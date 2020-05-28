# Copyright (C) 2016 OpenMotics BV
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
This module collects OpenMotics metrics and makes them available to the MetricsController
"""

from __future__ import absolute_import

import logging
import time
from collections import deque
from threading import Event, Thread

import six

from gateway.events import GatewayEvent
from gateway.maintenance_communicator import InMaintenanceModeException
from gateway.models import Database
from ioc import INJECTED, Inject, Injectable, Singleton
from platform_utils import Hardware
from power import power_api
from serial_utils import CommunicationTimedOutException

if False:  # MYPY
    from typing import Callable, Dict, Any, List, Optional, Tuple
    from gateway.input_controller import InputController
    from gateway.output_controller import OutputController
    from gateway.sensor_controller import SensorController
    from gateway.thermostat.thermostat_controller import ThermostatController
    from gateway.pulse_counter_controller import PulseCounterController
    from gateway.gateway_api import GatewayApi
    from gateway.dto import InputDTO, SensorDTO, OutputDTO, PulseCounterDTO

logger = logging.getLogger("openmotics")


@Injectable.named('metrics_collector')
@Singleton
class MetricsCollector(object):
    """
    The Metrics Collector collects OpenMotics metrics and makes them available.
    """

    OUTPUT_MODULE_TYPES = {'o': 'output',
                           'O': 'output',
                           'd': 'dimmer',
                           'D': 'dimmer'}
    OUTPUT_OUTPUT_TYPES = {0: 'outlet',
                           1: 'valve',
                           2: 'alarm',
                           3: 'appliance',
                           4: 'pump',
                           5: 'hvac',
                           6: 'generic',
                           7: 'motor',
                           8: 'ventilation',
                           255: 'light'}

    @Inject
    def __init__(self, gateway_api=INJECTED, pulse_counter_controller=INJECTED, thermostat_controller=INJECTED,
                 output_controller=INJECTED, input_controller=INJECTED, sensor_controller=INJECTED):
        self._start = time.time()
        self._last_service_uptime = 0
        self._stopped = True
        self._metrics_controller = None
        self._plugin_controller = None
        self._environment_inputs = {}  # type: Dict[int, InputDTO]
        self._environment_outputs = {}  # type: Dict[int, Tuple[OutputDTO, Dict[str, int]]]
        self._environment_sensors = {}  # type: Dict[int, SensorDTO]
        self._environment_pulse_counters = {}  # type: Dict[int, PulseCounterDTO]
        self._min_intervals = {'system': 60,
                               'output': 60,
                               'sensor': 5,
                               'thermostat': 30,
                               'error': 120,
                               'counter': 30,
                               'energy': 5,
                               'energy_analytics': 300}
        self.intervals = {metric_type: 900 for metric_type in self._min_intervals}
        self._plugin_intervals = {metric_type: [] for metric_type in self._min_intervals}  # type: Dict[str, List[Any]]
        self._websocket_intervals = {metric_type: {} for metric_type in self._min_intervals}  # type: Dict[str, Dict[Any, Any]]
        self._cloud_intervals = {metric_type: 900 for metric_type in self._min_intervals}
        self._sleepers = {metric_type: {'event': Event(),
                                        'start': 0,
                                        'end': 0} for metric_type in self._min_intervals}  # type: Dict[str,Dict[str,Any]]

        self._gateway_api = gateway_api  # type: GatewayApi
        self._thermostat_controller = thermostat_controller  # type: ThermostatController
        self._pulse_counter_controller = pulse_counter_controller  # type: PulseCounterController
        self._output_controller = output_controller  # type: OutputController
        self._input_controller = input_controller  # type: InputController
        self._sensor_controller = sensor_controller  # type: SensorController
        self._metrics_queue = deque()  # type: deque

    def start(self):
        self._start = time.time()
        self._stopped = False
        MetricsCollector._start_thread(self._load_environment_configurations, 'load_configuration', 900)
        MetricsCollector._start_thread(self._run_system, 'system')
        MetricsCollector._start_thread(self._run_outputs, 'output')
        MetricsCollector._start_thread(self._run_sensors, 'sensor')
        MetricsCollector._start_thread(self._run_thermostats, 'thermostat')
        MetricsCollector._start_thread(self._run_errors, 'error')
        MetricsCollector._start_thread(self._run_pulsecounters, 'counter')
        MetricsCollector._start_thread(self._run_power_openmotics, 'energy')
        MetricsCollector._start_thread(self._run_power_openmotics_analytics, 'energy_analytics')
        thread = Thread(target=self._sleep_manager)
        thread.setName('Metric collector - Sleep manager')
        thread.daemon = True
        thread.start()

    def stop(self):
        self._stopped = True

    def collect_metrics(self):
        # Yield all metrics in the Queue
        try:
            while True:
                yield self._metrics_queue.pop()
        except IndexError:
            pass

    def set_controllers(self, metrics_controller, plugin_controller):
        self._metrics_controller = metrics_controller
        self._plugin_controller = plugin_controller

    def set_cloud_interval(self, metric_type, interval):
        if metric_type not in self._min_intervals:  # e.g. event metric types
            return
        self._cloud_intervals[metric_type] = interval
        self._update_intervals(metric_type)

    def set_websocket_interval(self, client_id, metric_type, interval):
        if metric_type not in self._min_intervals:  # e.g. event metric types
            return
        assert self._metrics_controller
        metric_types = self._metrics_controller.get_filter('metric_type', metric_type)
        for mtype in self._websocket_intervals:
            if mtype in metric_types:
                if interval is None:
                    if client_id in self._websocket_intervals[mtype]:
                        del self._websocket_intervals[mtype][client_id]
                else:
                    self._websocket_intervals[mtype][client_id] = interval
                self._update_intervals(mtype)

    def set_plugin_intervals(self, plugin_intervals):
        assert self._metrics_controller
        for interval_info in plugin_intervals:
            sources = self._metrics_controller.get_filter('source', interval_info['source'])
            metric_types = self._metrics_controller.get_filter('metric_type', interval_info['metric_type'])
            if 'OpenMotics' not in sources:
                continue
            for metric_type in self.intervals:
                if metric_type == 'load_configuration':
                    continue
                if metric_type in metric_types:
                    self._plugin_intervals[metric_type].append(interval_info['interval'])
                    self._update_intervals(metric_type)

    def _update_intervals(self, metric_type):
        min_interval = self._min_intervals[metric_type]
        interval = max(min_interval, self._cloud_intervals[metric_type])
        if len(self._plugin_intervals[metric_type]) > 0:
            interval = min(interval, *[max(min_interval, i) for i in self._plugin_intervals[metric_type]])
        if len(self._websocket_intervals[metric_type]) > 0:
            interval = min(interval, *[max(min_interval, i) for i in self._websocket_intervals[metric_type].values()])
        self.intervals[metric_type] = interval
        self.maybe_wake_earlier(metric_type, interval)

    def _enqueue_metrics(self, metric_type, values, tags, timestamp):
        """
        metric_type = 'system'
        values = {'service_uptime': service_uptime},
        tags = {'name': 'gateway'}
        timestamp = 12346789
        """
        self._metrics_queue.appendleft({'source': 'OpenMotics',
                                        'type': metric_type,
                                        'timestamp': timestamp,
                                        'tags': tags,
                                        'values': values})

    def maybe_wake_earlier(self, metric_type, duration):
        if metric_type in self._sleepers:
            current_end = self._sleepers[metric_type]['end']
            new_end = self._sleepers[metric_type]['start'] + duration
            self._sleepers[metric_type]['end'] = min(current_end, new_end)

    def _sleep_manager(self):
        while True:
            for sleep_data in self._sleepers.values():
                if not sleep_data['event'].is_set() and sleep_data['end'] < time.time():
                    sleep_data['event'].set()
            time.sleep(0.1)

    @staticmethod
    def _start_thread(workload, name, interval=None):
        args = [name]
        if interval is not None:
            args.append(interval)
        thread = Thread(target=workload, args=args)
        thread.setName('Metric collector ({0})'.format(name))
        thread.daemon = True
        thread.start()
        return thread

    def _pause(self, start, metric_type, interval=None):
        if interval is None:
            interval = self.intervals[metric_type]
        if metric_type in self._sleepers:
            sleep_data = self._sleepers[metric_type]
            sleep_data['start'] = start
            sleep_data['end'] = start + interval
            sleep_data['event'].clear()
            sleep_data['event'].wait()
        else:
            elapsed = time.time() - start
            sleep = max(0.1, interval - elapsed)
            time.sleep(sleep)

    def process_observer_event(self, event):
        # type: (GatewayEvent) -> None
        if event.type == GatewayEvent.Types.OUTPUT_CHANGE:
            output_id = event.data['id']
            output_info = self._environment_outputs.get(output_id)
            if output_info is None:
                return
            output_dto, output_status = output_info
            output_status.update({'status': 1 if event.data['status']['on'] else 0,
                                  'dimmer': int(event.data['status'].get('value', 0))})
            self._process_outputs([output_id], 'output')
        if event.type == GatewayEvent.Types.INPUT_CHANGE:
            event_id = event.data['id']
            self._process_input(event_id, event.data.get('status'))

    def _process_outputs(self, output_ids, metric_type):
        try:
            now = time.time()
            outputs = self._environment_outputs
            for output_id in output_ids:
                output_info = outputs.get(output_id)
                if output_info is None:
                    continue
                output_dto, output_status = output_info
                output_name = output_dto.name
                status = output_status.get('status')
                dimmer = output_status.get('dimmer')
                if output_name != '' and status is not None and dimmer is not None:
                    if output_dto.module_type in ['O', 'o']:
                        level = 100
                    else:
                        level = dimmer
                    if status == 0:
                        level = 0
                    tags = {'id': output_id,
                            'name': output_name,
                            'module_type': MetricsCollector.OUTPUT_MODULE_TYPES[output_dto.module_type],
                            'type': MetricsCollector.OUTPUT_OUTPUT_TYPES[output_dto.output_type],
                            'floor': output_dto.floor}
                    self._enqueue_metrics(metric_type=metric_type,
                                          values={'value': int(level)},
                                          tags=tags,
                                          timestamp=now)
        except Exception as ex:
            logger.exception('Error processing outputs {0}: {1}'.format(output_ids, ex))

    def _process_input(self, input_id, status):
        try:
            now = time.time()
            inputs = self._environment_inputs
            if input_id not in inputs:
                return
            input_name = inputs[input_id].name
            if input_name != '':
                tags = {'type': 'input',
                        'id': input_id,
                        'name': input_name}
                self._enqueue_metrics(metric_type='event',
                                      values={'value': bool(status)},
                                      tags=tags,
                                      timestamp=now)
        except Exception as ex:
            logger.exception('Error processing input: {0}'.format(ex))

    def _run_system(self, metric_type):
        while not self._stopped:
            start = time.time()
            now = time.time()
            try:
                values = {}
                with open('/proc/uptime', 'r') as f:
                    system_uptime = float(f.readline().split()[0])
                service_uptime = time.time() - self._start
                if service_uptime > self._last_service_uptime + 3600:
                    self._start = time.time()
                    service_uptime = 0
                self._last_service_uptime = service_uptime

                values['service_uptime'] = float(service_uptime)
                values['system_uptime'] = float(system_uptime)

                try:
                    # On some older environments `psutil` doesn't work properly.
                    # Since these metrics are not critical they can be skipped
                    import psutil
                    collect_psutil_metrics = True
                except ImportError:
                    psutil = None
                    collect_psutil_metrics = False

                if collect_psutil_metrics:
                    try:
                        values['cpu_percent'] = float(psutil.cpu_percent())
                        cpu_load = [x / psutil.cpu_count() * 100 for x in psutil.getloadavg()]
                        values['cpu_load_1'] = float(cpu_load[0])
                        values['cpu_load_5'] = float(cpu_load[1])
                        values['cpu_load_15'] = float(cpu_load[2])
                    except Exception as ex:
                        logger.error('Error loading cpu metrics: {0}'.format(ex))

                    try:
                        memory = dict(psutil.virtual_memory()._asdict())
                        for reading in ['available', 'used', 'percent', 'free', 'inactive', 'shared', 'active', 'total']:
                            try:
                                key = 'memory_{0}'.format(reading)
                                value = memory[reading]
                                values[key] = int(value) if reading != 'percent' else float(value)
                            except Exception as ex:
                                logger.error('error loading memory metric: {0}'.format(ex))
                    except Exception as ex:
                        logger.error('Error loading memory metrics: {0}'.format(ex))

                    try:
                        disk = dict(psutil.disk_usage('/')._asdict())
                        for reading in ['total', 'used', 'percent', 'free']:
                            try:
                                key = 'disk_{0}'.format(reading)
                                value = disk[reading]
                                values[key] = int(value) if reading != 'percent' else float(value)
                            except Exception as ex:
                                logger.error('Error loading disk metric: {0}'.format(ex))

                        disk_io = dict(psutil.disk_io_counters()._asdict())
                        for reading in ['read_count', 'write_count', 'read_bytes', 'write_bytes']:
                            try:
                                key = 'disk_{0}'.format(reading)
                                value = disk_io[reading]
                                values[key] = int(value)
                            except Exception as ex:
                                logger.error('Error loading disk io metric: {0}'.format(ex))
                    except Exception as ex:
                        logger.error('Error loading disk metrics: {0}'.format(ex))

                    try:
                        network = dict(psutil.net_io_counters()._asdict())
                        for reading in ['bytes_sent', 'bytes_recv', 'packets_sent', 'packets_recv']:
                            try:
                                key = 'net_{0}'.format(reading)
                                value = network[reading]
                                values[key] = int(value)
                            except Exception as ex:
                                logger.error('Error loading network metric: {0}'.format(ex))
                    except Exception as ex:
                        logger.error('Error loading network metrics: {0}'.format(ex))

                try:
                    for key, val in Hardware.read_mmc_ext_csd().items():
                        values['disk_{}'.format(key)] = val
                except Exception as ex:
                    logger.error('Error loading disk eMMC metrics: {0}'.format(ex))

                # get database metrics
                try:
                    for model, counter in six.iteritems(Database.get_metrics()):
                        try:
                            key = 'db_{0}'.format(model)
                            values[key] = int(counter)
                        except Exception as ex:
                            logger.error('Error loading database metric: {0}'.format(ex))
                except Exception as ex:
                    logger.error('Error loading database metrics: {0}'.format(ex))

                self._enqueue_metrics(metric_type=metric_type,
                                      values=values,
                                      tags={'name': 'gateway',
                                            'section': 'main'},
                                      timestamp=now)
            except Exception as ex:
                logger.exception('Error sending system data: {0}'.format(ex))
            if self._metrics_controller is not None:
                try:
                    self._enqueue_metrics(metric_type=metric_type,
                                          tags={'name': 'gateway',
                                                'section': 'plugins'},
                                          values={'queue_length': len(self._metrics_controller.metrics_queue_plugins)},
                                          timestamp=now)
                    self._enqueue_metrics(metric_type=metric_type,
                                          tags={'name': 'gateway',
                                                'section': 'openmotics'},
                                          values={'queue_length': len(self._metrics_controller.metrics_queue_openmotics)},
                                          timestamp=now)
                    self._enqueue_metrics(metric_type=metric_type,
                                          tags={'name': 'gateway',
                                                'section': 'cloud'},
                                          values={'cloud_queue_length': self._metrics_controller.cloud_stats['queue'],
                                                  'cloud_buffer_length': self._metrics_controller.cloud_stats['buffer'],
                                                  'cloud_time_ago_send': self._metrics_controller.cloud_stats['time_ago_send'],
                                                  'cloud_time_ago_try': self._metrics_controller.cloud_stats['time_ago_try']},
                                          timestamp=now)
                    assert self._plugin_controller
                    for plugin in self._plugin_controller.get_plugins():
                        self._enqueue_metrics(metric_type=metric_type,
                                              tags={'name': 'gateway',
                                                    'section': plugin.name},
                                              values={'queue_length': plugin.get_queue_length()},
                                              timestamp=now)
                    for key in set(self._metrics_controller.inbound_rates.keys()) | set(self._metrics_controller.outbound_rates.keys()):
                        self._enqueue_metrics(metric_type=metric_type,
                                              tags={'name': 'gateway',
                                                    'section': key},
                                              values={'metrics_in': self._metrics_controller.inbound_rates.get(key, 0),
                                                      'metrics_out': self._metrics_controller.outbound_rates.get(key, 0)},
                                              timestamp=now)
                    for mtype in self.intervals:
                        self._enqueue_metrics(metric_type=metric_type,
                                              tags={'name': 'gateway',
                                                    'section': mtype},
                                              values={'metric_interval': self.intervals[mtype]},
                                              timestamp=now)
                except Exception as ex:
                    logger.error('Could not collect metric metrics: {0}'.format(ex))
            if self._stopped:
                return
            self._pause(start, metric_type)

    def _run_outputs(self, metric_type):
        while not self._stopped:
            start = time.time()
            try:
                result = self._gateway_api.get_outputs_status()
                for output in result:
                    output_id = output['id']
                    if output_id not in self._environment_outputs:
                        continue
                    output_dto, output_status = self._environment_outputs[output_id]
                    output_status.update({'status': output['status'],
                                          'dimmer': output['dimmer']})
            except CommunicationTimedOutException:
                logger.error('Error getting output status: CommunicationTimedOutException')
            except InMaintenanceModeException:
                logger.info('Error getting output status: InMaintenanceModeException')
            except Exception as ex:
                logger.exception('Error getting output status: {0}'.format(ex))
            self._process_outputs(list(self._environment_outputs.keys()), metric_type)
            if self._stopped:
                return
            self._pause(start, metric_type)

    def _run_sensors(self, metric_type):
        while not self._stopped:
            start = time.time()
            try:
                now = time.time()
                temperatures = self._gateway_api.get_sensors_temperature_status()
                humidities = self._gateway_api.get_sensors_humidity_status()
                brightnesses = self._gateway_api.get_sensors_brightness_status()
                for sensor_id, sensor_dto in self._environment_sensors.items():
                    name = sensor_dto.name
                    # TODO: Add a flag to the ORM to store this "in use" metadata
                    if name == '' or name == 'NOT_IN_USE':
                        continue
                    tags = {'id': sensor_id,
                            'name': name}
                    values = {}
                    if temperatures[sensor_id] is not None:
                        values['temp'] = temperatures[sensor_id]
                    if humidities[sensor_id] is not None:
                        values['hum'] = humidities[sensor_id]
                    if brightnesses[sensor_id] is not None:
                        values['bright'] = brightnesses[sensor_id]
                    if len(values) == 0:
                        continue
                    self._enqueue_metrics(metric_type=metric_type,
                                          values=values,
                                          tags=tags,
                                          timestamp=now)
            except CommunicationTimedOutException:
                logger.error('Error getting sensor status: CommunicationTimedOutException')
            except InMaintenanceModeException:
                logger.info('Error getting sensor status: InMaintenanceModeException')
            except Exception as ex:
                logger.exception('Error getting sensor status: {0}'.format(ex))
            if self._stopped:
                return
            self._pause(start, metric_type)

    def _run_thermostats(self, metric_type):
        while not self._stopped:
            start = time.time()
            try:
                now = time.time()
                thermostats = self._thermostat_controller.v0_get_thermostat_status()
                self._enqueue_metrics(metric_type=metric_type,
                                      values={'on': thermostats['thermostats_on'],
                                              'cooling': thermostats['cooling']},
                                      tags={'id': 'G.0',
                                            'name': 'Global configuration'},
                                      timestamp=now)
                for thermostat in thermostats['status']:
                    values = {'setpoint': int(thermostat['setpoint']),
                              'output0': float(thermostat['output0']),
                              'output1': float(thermostat['output1']),
                              'mode': int(thermostat['mode']),
                              'type': 'tbs' if thermostat['sensor_nr'] == 240 else 'normal',
                              'automatic': thermostat['automatic'],
                              'current_setpoint': thermostat['csetp']}
                    if thermostat['outside'] is not None:
                        values['outside'] = thermostat['outside']
                    if thermostat['sensor_nr'] != 240 and thermostat['act'] is not None:
                        values['temperature'] = thermostat['act']
                    self._enqueue_metrics(metric_type=metric_type,
                                          values=values,
                                          tags={'id': '{0}.{1}'.format('C' if thermostats['cooling'] is True else 'H',
                                                                       thermostat['id']),
                                                'name': thermostat['name']},
                                          timestamp=now)
            except CommunicationTimedOutException:
                logger.error('Error getting thermostat status: CommunicationTimedOutException')
            except InMaintenanceModeException:
                logger.info('Error getting thermostat status: InMaintenanceModeException')
            except Exception as ex:
                logger.exception('Error getting thermostat status: {0}'.format(ex))
            if self._stopped:
                return
            self._pause(start, metric_type)

    def _run_errors(self, metric_type):
        while not self._stopped:
            start = time.time()
            try:
                now = time.time()
                errors = self._gateway_api.master_error_list()
                for error in errors:
                    om_module = error[0]
                    count = error[1]
                    types = {'i': 'Input',
                             'I': 'Input',
                             't': 'Temperature',
                             'T': 'Temperature',
                             'o': 'Output',
                             'O': 'Output',
                             'd': 'Dimmer',
                             'D': 'Dimmer',
                             'R': 'Shutter',
                             'C': 'CAN',
                             'L': 'OLED'}
                    self._enqueue_metrics(metric_type=metric_type,
                                          values={'value': int(count)},
                                          tags={'type': types[om_module[0]],
                                                'id': om_module,
                                                'name': '{0} {1}'.format(types[om_module[0]], om_module)},
                                          timestamp=now)
            except CommunicationTimedOutException:
                logger.error('Error getting module errors: CommunicationTimedOutException')
            except InMaintenanceModeException:
                logger.info('Error getting module errors: InMaintenanceModeException')
            except Exception as ex:
                logger.exception('Error getting module errors: {0}'.format(ex))
            if self._stopped:
                return
            self._pause(start, metric_type)

    def _run_pulsecounters(self, metric_type):
        while not self._stopped:
            start = time.time()
            now = time.time()
            counters_data = {}
            try:
                for counter_id, counter_dto in self._environment_pulse_counters.items():
                    counters_data[counter_id] = {'name': counter_dto.name,
                                                 'input': counter_dto.input_id}
                values = self._pulse_counter_controller.get_values()
                for counter_id in counters_data:
                    if counter_id in values:
                        counters_data[counter_id]['count'] = values[counter_id]
                for counter_id in counters_data:
                    counter = counters_data[counter_id]
                    if counter['name'] != '' and counter['count'] is not None:
                        self._enqueue_metrics(metric_type=metric_type,
                                              values={'value': int(counter['count'])},
                                              tags={'name': counter['name'],
                                                    'input': counter['input'],
                                                    'id': 'P{0}'.format(counter_id)},
                                              timestamp=now)
            except CommunicationTimedOutException:
                logger.error('Error getting pulse counter status: CommunicationTimedOutException')
            except InMaintenanceModeException:
                logger.info('Error getting pulse counter status: InMaintenanceModeException')
            except Exception as ex:
                logger.exception('Error getting pulse counter status: {0}'.format(ex))
            if self._stopped:
                return
            self._pause(start, metric_type)

    def _run_power_openmotics(self, metric_type):
        # type: (str) -> None
        while not self._stopped:
            start = time.time()
            self._run_power_metrics(metric_type)
            if self._stopped:
                return
            self._pause(start, metric_type)

    def _run_power_metrics(self, metric_type):
        # type: (str) -> None
        def _add_if_not_none(dictionary, field, value):
            if value is not None:
                dictionary[field] = float(value)

        now = time.time()
        mapping = {}
        power_data = {}
        try:
            for power_module in self._gateway_api.get_power_modules():
                device_id = '{0}.{{0}}'.format(power_module['address'])
                mapping[str(power_module['id'])] = device_id
                for i in range(power_api.NUM_PORTS[power_module['version']]):
                    power_data[device_id.format(i)] = {'name': power_module['input{0}'.format(i)]}
        except CommunicationTimedOutException:
            logger.error('Error getting power modules: CommunicationTimedOutException')
        except InMaintenanceModeException:
            logger.info('Error getting power modules: InMaintenanceModeException')
        except Exception as ex:
            logger.exception('Error getting power modules: {0}'.format(ex))
        try:
            realtime_power_data = self._gateway_api.get_realtime_power()
            for module_id, device_id in mapping.items():
                if module_id in realtime_power_data:
                    for index, realtime_power in enumerate(realtime_power_data[module_id]):
                        if device_id.format(index) in power_data:
                            usage = power_data[device_id.format(index)]
                            _add_if_not_none(usage, 'voltage', realtime_power.voltage)
                            _add_if_not_none(usage, 'frequency', realtime_power.frequency)
                            _add_if_not_none(usage, 'current', realtime_power.current)
                            _add_if_not_none(usage, 'power', realtime_power.power)
        except CommunicationTimedOutException:
            logger.error('Error getting realtime power: CommunicationTimedOutException')
        except InMaintenanceModeException:
            logger.info('Error getting realtime power: InMaintenanceModeException')
        except Exception as ex:
            logger.exception('Error getting realtime power: {0}'.format(ex))
        try:
            realtime_p1_data = self._gateway_api.get_realtime_p1()
            for module_id, device_id in mapping.items():
                for realtime_p1 in realtime_p1_data:
                    if str(realtime_p1['module_id']) == module_id:
                        self._enqueue_metrics(metric_type='energy_p1',
                                              values={'voltage_phase1': realtime_p1['voltage']['phase1'],
                                                      'voltage_phase2': realtime_p1['voltage']['phase2'],
                                                      'voltage_phase3': realtime_p1['voltage']['phase3'],
                                                      'current_phase1': realtime_p1['current']['phase1'],
                                                      'current_phase2': realtime_p1['current']['phase2'],
                                                      'current_phase3': realtime_p1['current']['phase3']},
                                              tags={'type': 'openmotics',
                                                    'id': device_id.format(realtime_p1['port_id']),
                                                    'meter': realtime_p1['meter']},
                                              timestamp=now)
        except CommunicationTimedOutException:
            logger.error('Error getting realtime power: CommunicationTimedOutException')
        except InMaintenanceModeException:
            logger.info('Error getting realtime power: InMaintenanceModeException')
        except Exception as ex:
            logger.exception('Error getting realtime power: {0}'.format(ex))
        try:
            total_energy = self._gateway_api.get_total_energy()
            for module_id, device_id in mapping.items():
                if module_id in total_energy:
                    for index, entry in enumerate(total_energy[module_id]):
                        day, night = entry
                        total = None
                        if day is not None and night is not None:
                            total = day + night
                        if device_id.format(index) in power_data:
                            usage = power_data[device_id.format(index)]
                            _add_if_not_none(usage, 'counter', total)
                            _add_if_not_none(usage, 'counter_day', day)
                            _add_if_not_none(usage, 'counter_night', night)
        except CommunicationTimedOutException:
            logger.error('Error getting total energy: CommunicationTimedOutException')
        except InMaintenanceModeException:
            logger.info('Error getting total energy: InMaintenanceModeException')
        except Exception as ex:
            logger.exception('Error getting total energy: {0}'.format(ex))
        for device_id in power_data:
            device = power_data[device_id]
            try:
                if device['name'] != '' and len(device) > 1:
                    name = device.pop('name')
                    self._enqueue_metrics(metric_type=metric_type,
                                          values=device,
                                          tags={'type': 'openmotics',
                                                'id': device_id,
                                                'name': name},
                                          timestamp=now)
            except Exception as ex:
                logger.exception('Error processing OpenMotics power device {0}: {1}'.format(device_id, ex))

    def _run_power_openmotics_analytics(self, metric_type):
        while not self._stopped:
            start = time.time()
            try:
                now = time.time()
                result = self._gateway_api.get_power_modules()
                for power_module in result:
                    device_id = '{0}.{{0}}'.format(power_module['address'])
                    if power_module['version'] != power_api.ENERGY_MODULE:
                        continue
                    result = self._gateway_api.get_energy_time(power_module['id'])
                    abort = False
                    for i in range(12):
                        if abort is True:
                            break
                        name = power_module['input{0}'.format(i)]
                        if name == '':
                            continue
                        timestamp = now
                        length = min(len(result[str(i)]['current']), len(result[str(i)]['voltage']))
                        for j in range(length):
                            self._enqueue_metrics(metric_type=metric_type,
                                                  values={'current': result[str(i)]['current'][j],
                                                          'voltage': result[str(i)]['voltage'][j]},
                                                  tags={'id': device_id.format(i),
                                                        'name': name,
                                                        'type': 'time'},
                                                  timestamp=timestamp)
                            timestamp += 0.250  # Stretch actual data by 1000 for visualtisation purposes
                    result = self._gateway_api.get_energy_frequency(power_module['id'])
                    abort = False
                    for i in range(12):
                        if abort is True:
                            break
                        name = power_module['input{0}'.format(i)]
                        if name == '':
                            continue
                        timestamp = now
                        length = min(len(result[str(i)]['current'][0]), len(result[str(i)]['voltage'][0]))
                        for j in range(length):
                            self._enqueue_metrics(metric_type=metric_type,
                                                  values={'current_harmonics': result[str(i)]['current'][0][j],
                                                          'current_phase': result[str(i)]['current'][1][j],
                                                          'voltage_harmonics': result[str(i)]['voltage'][0][j],
                                                          'voltage_phase': result[str(i)]['voltage'][1][j]},
                                                  tags={'id': device_id.format(i),
                                                        'name': name,
                                                        'type': 'frequency'},
                                                  timestamp=timestamp)
                            timestamp += 0.250  # Stretch actual data by 1000 for visualtisation purposes
            except CommunicationTimedOutException:
                logger.error('Error getting power analytics: CommunicationTimedOutException')
            except InMaintenanceModeException:
                logger.info('Error getting power analytics: InMaintenanceModeException')
            except Exception as ex:
                logger.exception('Error getting power analytics: {0}'.format(ex))
            if self._stopped:
                return
            self._pause(start, metric_type)

    def _load_environment_configurations(self, name, interval):  # type: (str, int) -> None
        while not self._stopped:
            start = time.time()
            # Inputs
            try:
                inputs = self._input_controller.load_inputs()
                ids = []
                for input_dto in inputs:
                    input_id = input_dto.id
                    ids.append(input_id)
                    self._environment_inputs[input_id] = input_dto
                for input_id in self._environment_inputs.keys():
                    if input_id not in ids:
                        del self._environment_inputs[input_id]
            except CommunicationTimedOutException:
                logger.error('Error while loading input configurations: CommunicationTimedOutException')
            except InMaintenanceModeException:
                logger.info('Error while loading input configurations: InMaintenanceModeException')
            except Exception as ex:
                logger.exception('Error while loading input configurations: {0}'.format(ex))
            # Outputs
            try:
                outputs = self._output_controller.load_outputs()
                ids = []
                for output_dto in outputs:
                    if output_dto.module_type not in ['o', 'O', 'd', 'D']:
                        continue
                    output_id = output_dto.id
                    ids.append(output_id)
                    # TODO: Don't cache the status here, but ask it to the OutputController when relevant
                    self._environment_outputs[output_id] = (output_dto, {})
                for output_id in self._environment_outputs.keys():
                    if output_id not in ids:
                        del self._environment_outputs[output_id]
            except CommunicationTimedOutException:
                logger.error('Error while loading output configurations: CommunicationTimedOutException')
            except InMaintenanceModeException:
                logger.info('Error while loading output configurations: InMaintenanceModeException')
            except Exception as ex:
                logger.exception('Error while loading output configurations: {0}'.format(ex))
            # Sensors
            try:
                sensors = self._sensor_controller.load_sensors()
                ids = []
                for sensor_dto in sensors:
                    sensor_id = sensor_dto.id
                    ids.append(sensor_id)
                    self._environment_sensors[sensor_id] = sensor_dto
                for sensor_id in self._environment_sensors.keys():
                    if sensor_id not in ids:
                        del self._environment_sensors[sensor_id]
            except CommunicationTimedOutException:
                logger.error('Error while loading sensor configurations: CommunicationTimedOutException')
            except InMaintenanceModeException:
                logger.info('Error while loading sensor configurations: InMaintenanceModeException')
            except Exception as ex:
                logger.exception('Error while loading sensor configurations: {0}'.format(ex))
            # Pulse counters
            try:
                pulse_counters = self._pulse_counter_controller.load_pulse_counters()
                ids = []
                for pulse_counter_dto in pulse_counters:
                    pulse_counter_id = pulse_counter_dto.id
                    ids.append(pulse_counter_id)
                    self._environment_pulse_counters[pulse_counter_id] = pulse_counter_dto
                for pulse_counter_id in self._environment_pulse_counters.keys():
                    if pulse_counter_id not in ids:
                        del self._environment_pulse_counters[pulse_counter_id]
            except CommunicationTimedOutException:
                logger.error('Error while loading pulse counter configurations: CommunicationTimedOutException')
            except InMaintenanceModeException:
                logger.info('Error while loading pulse counter configurations: InMaintenanceModeException')
            except Exception as ex:
                logger.exception('Error while loading pulse counter configurations: {0}'.format(ex))
            if self._stopped:
                return
            self._pause(start, name, interval)

    def get_definitions(self):
        """
        > example_definition = {"type": "energy",
        >                       "tags": ["device", "id"],
        >                       "metrics": [{"name": "power",
        >                                    "description": "Total energy consumed (in kWh)",
        >                                    "type": "counter",
        >                                    "unit": "kWh"}]}
        """
        pulse_persistence = self._pulse_counter_controller.get_persistence()  # type: Dict[int, bool]
        db_definitions = [{'name': database_model,
                           'description': database_model,
                           'type': 'counter',
                           'unit': ''} for database_model in Database.get_models()]
        return [
            # system
            {'type': 'system',
             'tags': ['name', 'section'],
             'metrics': [{'name': 'service_uptime',
                          'description': 'Service uptime',
                          'type': 'gauge',
                          'unit': 's'},
                         {'name': 'system_uptime',
                          'description': 'System uptime',
                          'type': 'gauge',
                          'unit': 's'},
                         {'name': 'cpu_percent',
                          'description': 'System cpu percentage',
                          'type': 'gauge',
                          'unit': 'percent'},
                         {'name': 'cpu_load_1',
                          'description': 'System cpu load over 1 minute',
                          'type': 'gauge',
                          'unit': ''},
                         {'name': 'cpu_load_5',
                          'description': 'System cpu load over 5 minutes',
                          'type': 'gauge',
                          'unit': ''},
                         {'name': 'cpu_load_15',
                          'description': 'System cpu load over 15 minutes',
                          'type': 'gauge',
                          'unit': ''},
                         {'name': 'memory_available',
                          'description': 'Available memory',
                          'type': 'gauge',
                          'unit': 'bytes'},
                         {'name': 'memory_used',
                          'description': 'Used memory',
                          'type': 'gauge',
                          'unit': 'bytes'},
                         {'name': 'memory_percent',
                          'description': 'Memory percentage',
                          'type': 'gauge',
                          'unit': 'percent'},
                         {'name': 'memory_free',
                          'description': 'Free memory',
                          'type': 'gauge',
                          'unit': 'bytes'},
                         {'name': 'memory_inactive',
                          'description': 'Inactive memory',
                          'type': 'gauge',
                          'unit': 'bytes'},
                         {'name': 'memory_shared',
                          'description': 'Wired memory',
                          'type': 'gauge',
                          'unit': 'bytes'},
                         {'name': 'memory_active',
                          'description': 'Active memory',
                          'type': 'gauge',
                          'unit': 'bytes'},
                         {'name': 'memory_total',
                          'description': 'Total memory',
                          'type': 'gauge',
                          'unit': 'bytes'},
                         {'name': 'disk_total',
                          'description': 'Total disk',
                          'type': 'gauge',
                          'unit': 'bytes'},
                         {'name': 'disk_used',
                          'description': 'Disk used',
                          'type': 'gauge',
                          'unit': 'bytes'},
                         {'name': 'disk_free',
                          'description': 'Free disk',
                          'type': 'gauge',
                          'unit': 'bytes'},
                         {'name': 'disk_percent',
                          'description': 'Disk percentage',
                          'type': 'gauge',
                          'unit': 'percent'},
                         {'name': 'disk_read_count',
                          'description': 'Disk read count',
                          'type': 'gauge',
                          'unit': ''},
                         {'name': 'disk_write_count',
                          'description': 'Disk write count',
                          'type': 'gauge',
                          'unit': ''},
                         {'name': 'disk_read_bytes',
                          'description': 'Disk read bytes',
                          'type': 'gauge',
                          'unit': 'bytes'},
                         {'name': 'disk_write_bytes',
                          'description': 'Disk write bytes',
                          'type': 'gauge',
                          'unit': 'bytes'},
                         {'name': 'disk_life_time_est_typ_b',
                          'description': 'Disk eMMC Life Time Estimation B',
                          'type': 'gauge',
                          'unit': ''},
                         {'name': 'disk_life_time_est_typ_a',
                          'description': 'Disk eMMC Life Time Estimation A',
                          'type': 'gauge',
                          'unit': ''},
                         {'name': 'disk_eol_info',
                          'description': 'eMMC Pre EOL information',
                          'type': 'gauge',
                          'unit': ''},
                         {'name': 'net_bytes_sent',
                          'description': 'Network bytes sent',
                          'type': 'gauge',
                          'unit': 'bytes'},
                         {'name': 'net_bytes_recv',
                          'description': 'Network bytes received',
                          'type': 'gauge',
                          'unit': 'bytes'},
                         {'name': 'net_packets_sent',
                          'description': 'Network packets sent',
                          'type': 'gauge',
                          'unit': ''},
                         {'name': 'net_packets_recv',
                          'description': 'Network packets received',
                          'type': 'gauge',
                          'unit': ''},
                         {'name': 'metrics_in',
                          'description': 'Inbound metrics processed',
                          'type': 'counter',
                          'unit': ''},
                         {'name': 'metrics_out',
                          'description': 'Outbound metrics processed',
                          'type': 'counter',
                          'unit': ''},
                         {'name': 'queue_length',
                          'description': 'Metrics queue length',
                          'type': 'gauge',
                          'unit': ''},
                         {'name': 'metric_interval',
                          'description': 'Interval on which OM metrics are collected',
                          'type': 'gauge',
                          'unit': 'seconds'},
                         {'name': 'cloud_queue_length',
                          'description': 'Length of the memory queue of metrics to be send to the Cloud',
                          'type': 'gauge',
                          'unit': ''},
                         {'name': 'cloud_buffer_length',
                          'description': 'Length of the on-disk buffer of metrics to be send to the Cloud',
                          'type': 'gauge',
                          'unit': ''},
                         {'name': 'cloud_time_ago_send',
                          'description': 'Time passed since the last time metrics were send to the Cloud',
                          'type': 'gauge',
                          'unit': 'seconds'},
                         {'name': 'cloud_time_ago_try',
                          'description': 'Time passed since the last try sending metrics to the Cloud',
                          'type': 'gauge',
                          'unit': 'seconds'}] + db_definitions},
            # inputs / events
            {'type': 'event',
             'tags': ['type', 'id', 'name'],
             'metrics': [{'name': 'value',
                          'description': 'OpenMotics event',
                          'type': 'gauge',
                          'unit': 'event'}]},
            # output
            {'type': 'output',
             'tags': ['id', 'name', 'module_type', 'type', 'floor'],
             'metrics': [{'name': 'value',
                          'description': 'Output state',
                          'type': 'gauge',
                          'unit': ''}]},
            # sensor
            {'type': 'sensor',
             'tags': ['id', 'name'],
             'metrics': [{'name': 'temp',
                          'description': 'Temperature',
                          'type': 'gauge',
                          'unit': 'degree C'},
                         {'name': 'hum',
                          'description': 'Humidity',
                          'type': 'gauge',
                          'unit': '%'},
                         {'name': 'bright',
                          'description': 'Brightness',
                          'type': 'gauge',
                          'unit': '%'}]},
            # thermostat
            {'type': 'thermostat',
             'tags': ['id', 'name'],
             'metrics': [{'name': 'on',
                          'description': 'Indicates whether the thermostat is on',
                          'type': 'gauge',
                          'unit': ''},
                         {'name': 'cooling',
                          'description': 'Indicates whether the thermostat is on cooling',
                          'type': 'gauge',
                          'unit': ''},
                         {'name': 'setpoint',
                          'description': 'Setpoint identifier (values 0-5)',
                          'type': 'gauge',
                          'unit': ''},
                         {'name': 'output0',
                          'description': 'State of the primary output valve',
                          'type': 'gauge',
                          'unit': ''},
                         {'name': 'output1',
                          'description': 'State of the secondairy output valve',
                          'type': 'gauge',
                          'unit': ''},
                         {'name': 'mode',
                          'description': 'Thermostat mode',
                          'type': 'gauge',
                          'unit': ''},
                         {'name': 'type',
                          'description': 'Thermostat type',
                          'type': 'gauge',
                          'unit': ''},
                         {'name': 'automatic',
                          'description': 'Automatic indicator',
                          'type': 'gauge',
                          'unit': ''},
                         {'name': 'current_setpoint',
                          'description': 'Current setpoint',
                          'type': 'gauge',
                          'unit': 'degree C'},
                         {'name': 'outside',
                          'description': 'Outside sensor value',
                          'type': 'gauge',
                          'unit': 'degree C'},
                         {'name': 'temperature',
                          'description': 'Current temperature',
                          'type': 'gauge',
                          'unit': 'degree C'}]},
            # error
            {'type': 'error',
             'tags': ['type', 'id', 'name'],
             'metrics': [{'name': 'value',
                          'description': 'Amount of errors',
                          'type': 'gauge',
                          'unit': ''}]},
            # counter
            {'type': 'counter',
             'tags': ['name', 'input'],
             'metrics': [{'name': 'value',
                          'description': 'Number of received pulses',
                          'type': 'counter',
                          'policies': [{'policy': 'persist',
                                        'key': 'id',
                                        'matches': ['P{0}'.format(i)
                                                    for i in pulse_persistence
                                                    if not pulse_persistence[i]]},
                                       'buffer'],
                          'unit': ''}]},
            # energy
            {'type': 'energy',
             'tags': ['type', 'id', 'name'],
             'metrics': [{'name': 'voltage',
                          'description': 'Current voltage',
                          'type': 'gauge',
                          'unit': 'V'},
                         {'name': 'current',
                          'description': 'Current current',
                          'type': 'gauge',
                          'unit': 'A'},
                         {'name': 'frequency',
                          'description': 'Current frequency',
                          'type': 'gauge',
                          'unit': 'Hz'},
                         {'name': 'power',
                          'description': 'Current power consumption',
                          'type': 'gauge',
                          'unit': 'W'},
                         {'name': 'counter',
                          'description': 'Total energy consumed',
                          'type': 'counter',
                          'policies': ['buffer'],
                          'unit': 'Wh'},
                         {'name': 'counter_day',
                          'description': 'Total energy consumed during daytime',
                          'type': 'counter',
                          'policies': ['buffer'],
                          'unit': 'Wh'},
                         {'name': 'counter_night',
                          'description': 'Total energy consumed during nighttime',
                          'type': 'counter',
                          'policies': ['buffer'],
                          'unit': 'Wh'}]},
            # energy_p1
            {'type': 'energy_p1',
             'tags': ['id', 'meter', 'type'],
             'metrics': [{'name': 'voltage_phase1',
                          'description': 'Current phase1 voltage',
                          'type': 'gauge',
                          'unit': 'V'},
                         {'name': 'voltage_phase2',
                          'description': 'Current phase2 voltage',
                          'type': 'gauge',
                          'unit': 'V'},
                         {'name': 'voltage_phase3',
                          'description': 'Current phase3 voltage',
                          'type': 'gauge',
                          'unit': 'V'},
                         {'name': 'current_phase1',
                          'description': 'Current phase1 current',
                          'type': 'gauge',
                          'unit': 'A'},
                         {'name': 'current_phase2',
                          'description': 'Current phase2 current',
                          'type': 'gauge',
                          'unit': 'A'},
                         {'name': 'current_phase3',
                          'description': 'Current phase3 current',
                          'type': 'gauge',
                          'unit': 'A'}]},
            # energy_analytics
            {'type': 'energy_analytics',
             'tags': ['id', 'name', 'type'],
             'metrics': [{'name': 'current',
                          'description': 'Time-based current',
                          'type': 'gauge',
                          'unit': 'A'},
                         {'name': 'voltage',
                          'description': 'Time-based voltage',
                          'type': 'gauge',
                          'unit': 'V'},
                         {'name': 'current_harmonics',
                          'description': 'Current harmonics',
                          'type': 'gauge',
                          'unit': ''},
                         {'name': 'current_phase',
                          'description': 'Current phase',
                          'type': 'gauge',
                          'unit': ''},
                         {'name': 'voltage_harmonics',
                          'description': 'Voltage harmonics',
                          'type': 'gauge',
                          'unit': ''},
                         {'name': 'voltage_phase',
                          'description': 'Voltage phase',
                          'type': 'gauge',
                          'unit': ''}]}
        ]
