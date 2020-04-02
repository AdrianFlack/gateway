# Copyright (C) 2019 OpenMotics BV
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
Module for communicating with the Master
"""
import logging
import time
from threading import Thread

from gateway.enums import ShutterEnums
from gateway.dto import OutputDTO, ShutterDTO, ShutterGroupDTO
from gateway.hal.mappers_core import OutputMapper, ShutterMapper
from gateway.hal.master_controller import MasterController
from gateway.hal.master_event import MasterEvent
from gateway.maintenance_communicator import InMaintenanceModeException
from ioc import INJECTED, Inject, Injectable, Singleton
from master_core.core_api import CoreAPI
from master_core.core_communicator import BackgroundConsumer, CoreCommunicator
from master_core.ucan_communicator import UCANCommunicator
from master_core.errors import Error
from master_core.events import Event as MasterCoreEvent
from master_core.memory_file import MemoryTypes, MemoryFile
from master_core.memory_models import (
    GlobalConfiguration, InputConfiguration, OutputConfiguration,
    SensorConfiguration, ShutterConfiguration
)
from serial_utils import CommunicationTimedOutException

if False:  # MYPY
    from typing import Any, Dict, List, Tuple

logger = logging.getLogger("openmotics")


@Injectable.named('master_controller')
@Singleton
class MasterCoreController(MasterController):

    @Inject
    def __init__(self, master_communicator=INJECTED, ucan_communicator=INJECTED, memory_files=INJECTED):
        super(MasterCoreController, self).__init__(master_communicator)
        self._master_communicator = master_communicator  # type: CoreCommunicator
        self._ucan_communicator = ucan_communicator  # type: UCANCommunicator
        self._memory_files = memory_files  # type: Dict[str, MemoryFile]
        self._synchronization_thread = Thread(target=self._synchronize, name='CoreMasterSynchronization')
        self._master_online = False
        self._input_state = MasterInputState()
        self._output_interval = 600
        self._output_last_updated = 0
        self._output_states = {}
        self._sensor_interval = 300
        self._sensor_last_updated = 0
        self._sensor_states = {}
        self._shutters_interval = 600
        self._shutters_last_updated = 0
        self._output_shutter_map = {}  # type: Dict[int, int]

        self._memory_files[MemoryTypes.EEPROM].subscribe_eeprom_change(self._handle_eeprom_change)

        self._master_communicator.register_consumer(
            BackgroundConsumer(CoreAPI.event_information(), 0, self._handle_event)
        )
        self._master_communicator.register_consumer(
            BackgroundConsumer(CoreAPI.error_information(), 0, lambda e: logger.info('Got master error: {0}'.format(Error(e))))
        )
        self._master_communicator.register_consumer(
            BackgroundConsumer(CoreAPI.ucan_module_information(), 0, lambda i: logger.info('Got ucan module information: {0}'.format(i)))
        )

    #################
    # Private stuff #
    #################

    def _handle_eeprom_change(self):
        self._output_shutter_map = {}
        self._shutters_last_updated = 0
        self._sensor_last_updated = 0
        self._input_last_updated = 0
        self._output_last_updated = 0
        event = MasterEvent(event_type=MasterEvent.Types.EEPROM_CHANGE,
                            data=None)
        for callback in self._event_callbacks:
            callback(event)

    def _handle_event(self, data):
        # type: (Dict[str,Any]) -> None
        core_event = MasterCoreEvent(data)
        if core_event.type not in [MasterCoreEvent.Types.LED_BLINK,
                                   MasterCoreEvent.Types.LED_ON]:
            # Interesting for debug purposes, but not for everything
            logger.info('Got master event: {0}'.format(core_event))
        if core_event.type == MasterCoreEvent.Types.OUTPUT:
            # Update internal state cache
            output_id = core_event.data['output']
            timer_value = core_event.data['timer_value']
            if timer_value is not None:
                timer_value *= core_event.data['timer_factor']
            self._process_new_output_state(output_id=output_id,
                                           status=core_event.data['status'],
                                           timer=timer_value,
                                           dimmer=core_event.data['dimmer_value'])
        elif core_event.type == MasterCoreEvent.Types.INPUT:
            event = self._input_state.handle_event(core_event)
            for callback in self._event_callbacks:
                callback(event)
        elif core_event.type == MasterCoreEvent.Types.SENSOR:
            sensor_id = core_event.data['sensor']
            if sensor_id not in self._sensor_states:
                return
            self._sensor_states[sensor_id][core_event.data['type']] = core_event.data['value']

    def _process_new_output_state(self, output_id, status, timer, dimmer):
        new_state = {'id': output_id,
                     'status': 1 if status else 0,
                     'ctimer': timer,
                     'dimmer': dimmer}
        current_state = self._output_states.get(output_id)
        if current_state is not None:
            if current_state['status'] == new_state['status'] and current_state['dimmer'] == new_state['dimmer']:
                return
        self._output_states[output_id] = new_state
        # Generate generic event
        event = MasterEvent(event_type=MasterEvent.Types.OUTPUT_CHANGE,
                            data={'id': output_id,
                                  'status': {'on': status,
                                             'value': dimmer},
                                  'location': {'room_id': 255}})  # TODO: Missing room
        for callback in self._event_callbacks:
            callback(event)
        # Handle shutter events, if needed
        shutter_id = self._output_shutter_map.get(output_id)
        if shutter_id is not None:
            self._refresh_shutter_state(shutter_id)

    def _synchronize(self):
        # type: () -> None
        while True:
            try:
                # Refresh if required
                if self._refresh_input_states():
                    self._set_master_state(True)
                if self._output_last_updated + self._output_interval < time.time():
                    self._refresh_output_states()
                    self._set_master_state(True)
                if self._sensor_last_updated + self._sensor_interval < time.time():
                    self._refresh_sensor_states()
                    self._set_master_state(True)
                if self._shutters_last_updated + self._shutters_interval < time.time():
                    self._refresh_shutter_states()
                    self._set_master_state(True)
                time.sleep(1)
            except CommunicationTimedOutException:
                logger.error('Got communication timeout during synchronization, waiting 10 seconds.')
                self._set_master_state(False)
                time.sleep(10)
            except InMaintenanceModeException:
                # This is an expected situation
                time.sleep(10)
            except Exception as ex:
                logger.exception('Unexpected error during synchronization: {0}'.format(ex))
                time.sleep(10)

    def _set_master_state(self, online):
        if online != self._master_online:
            self._master_online = online

    def _serialize_input(self, input_module, fields=None):
        data = {'id': input_module.id}
        if fields is None or 'name' in fields:
            data['name'] = input_module.name
        if fields is None or 'module_type' in fields:
            data['module_type'] = input_module.module.device_type
        return data

    def _enumerate_io_modules(self, module_type, amount_per_module=8):
        cmd = CoreAPI.general_configuration_number_of_modules()
        module_count = self._master_communicator.do_command(cmd, {})[module_type]
        return xrange(module_count * amount_per_module)

    #######################
    # Internal management #
    #######################

    def start(self):
        super(MasterCoreController, self).start()
        self._synchronization_thread.start()
        self._log_stats()

    def set_plugin_controller(self, plugin_controller):
        """ Set the plugin controller. """
        pass  # TODO: implement

    def _log_stats(self):
        def _default_if_255(value, default):
            return value if value != 255 else default

        max_specs = self._master_communicator.do_command(CoreAPI.general_configuration_max_specs(), {})
        general_configuration = GlobalConfiguration()
        logger.info('General core information:')
        logger.info('* Modules:')
        logger.info('  * Output: {0}/{1}'.format(_default_if_255(general_configuration.number_of_output_modules, 0),
                                                 max_specs['output']))
        logger.info('  * Input: {0}/{1}'.format(_default_if_255(general_configuration.number_of_input_modules, 0),
                                                max_specs['input']))
        logger.info('  * Sensor: {0}/{1}'.format(_default_if_255(general_configuration.number_of_sensor_modules, 0),
                                                 max_specs['sensor']))
        logger.info('  * uCAN: {0}/{1}'.format(_default_if_255(general_configuration.number_of_ucan_modules, 0),
                                               max_specs['ucan']))
        logger.info('  * CAN Control: {0}'.format(_default_if_255(general_configuration.number_of_can_control_modules, 0)))
        logger.info('* CAN:')
        logger.info('  * Inputs: {0}'.format(general_configuration.number_of_can_inputs))
        logger.info('  * Sensors: {0}'.format(general_configuration.number_of_can_sensors))
        logger.info('* Scan times:')
        logger.info('  * General bus: {0}ms'.format(_default_if_255(general_configuration.scan_time_rs485_bus, 8)))
        logger.info('  * Sensor modules: {0}ms'.format(_default_if_255(general_configuration.scan_time_rs485_sensor_modules, 50) * 100))
        logger.info('  * CAN Control modules: {0}ms'.format(_default_if_255(general_configuration.scan_time_rs485_can_control_modules, 50) * 100))
        logger.info('* Runtime stats:')
        logger.info('  * Uptime: {0}d {1}h'.format(general_configuration.uptime_hours / 24,
                                                   general_configuration.uptime_hours % 24))
        # noinspection PyStringFormat
        logger.info('  * Started at 20{0}/{1}/{2} {3}:{4}:{5}'.format(*(list(reversed(general_configuration.startup_date)) +
                                                                        general_configuration.startup_time)))

    ##############
    # Public API #
    ##############

    def invalidate_caches(self):
        # type: () -> None
        self._input_last_updated = 0
        self._output_last_updated = 0

    def get_firmware_version(self):
        return 0, 0, 0  # TODO

    # Memory (eeprom/fram)

    def eeprom_read_page(self, page):
        return self._memory_files[MemoryTypes.EEPROM].read_page(page)

    def fram_read_page(self, page):
        return self._memory_files[MemoryTypes.FRAM].read_page(page)

    # Input

    def get_input_module_type(self, input_module_id):
        input_module = InputConfiguration(input_module_id)
        return input_module.module.device_type

    def get_inputs_with_status(self):
        # type: () -> List[Dict[str,Any]]
        return self._input_state.get_inputs()

    def get_recent_inputs(self):
        # type: () -> List[int]
        return self._input_state.get_recent()

    def load_input(self, input_module_id, fields=None):
        input_module = InputConfiguration(input_module_id)
        module_type = input_module.module.device_type
        if module_type not in ['i', 'I']:
            raise TypeError('The given id {0} is not an input, but {1}'.format(input_module_id, module_type))
        return self._serialize_input(input_module, fields=fields)

    def load_inputs(self, fields=None):
        inputs = []
        for i in self._enumerate_io_modules('input'):
            input_module = InputConfiguration(i)
            module_type = input_module.module.device_type
            if module_type in ['i', 'I']:
                input_data = self._serialize_input(input_module, fields=fields)
                inputs.append(input_data)
        return inputs

    def save_inputs(self, data, fields=None):
        for input_data in data:
            new_data = {'id': input_data['id'],
                        'name': input_data['name']}
            input_module = InputConfiguration.deserialize(new_data)
            input_module.save()

    def _refresh_input_states(self):
        # type: () -> bool
        refresh = self._input_state.should_refresh()
        if refresh:
            cmd = CoreAPI.device_information_list_inputs()
            data = self._master_communicator.do_command(cmd, {})
            for event in self._input_state.refresh(data['information']):
                for callback in self._event_callbacks:
                    callback(event)
        return refresh

    # Outputs

    def set_output(self, output_id, state, dimmer=None, timer=None):
        output = OutputConfiguration(output_id)
        if output.is_shutter:
            # Shutter outputs cannot be controlled
            return
        _ = dimmer, timer  # TODO: Use `dimmer` and `timer`
        action = 1 if state else 0
        self._master_communicator.do_command(CoreAPI.basic_action(), {'type': 0, 'action': action,
                                                                      'device_nr': output_id,
                                                                      'extra_parameter': 0})

    def toggle_output(self, output_id):
        output = OutputConfiguration(output_id)
        if output.is_shutter:
            # Shutter outputs cannot be controlled
            return
        self._master_communicator.do_command(CoreAPI.basic_action(), {'type': 0, 'action': 16,
                                                                      'device_nr': output_id,
                                                                      'extra_parameter': 0})

    def load_output(self, output_id):  # type: (int) -> OutputDTO
        output = OutputConfiguration(output_id)
        if output.is_shutter:
            # Outputs that are used by a shutter are returned as unconfigured (read-only) outputs
            return OutputDTO(id=output.id)
        return OutputMapper.orm_to_dto(output)

    def load_outputs(self):  # type: () -> List[OutputDTO]
        outputs = []
        for i in self._enumerate_io_modules('output'):
            outputs.append(self.load_output(i))
        return outputs

    def save_outputs(self, outputs):  # type: (List[Tuple[OutputDTO, List[str]]]) -> None
        for output_dto, fields in outputs:
            output = OutputMapper.dto_to_orm(output_dto, fields)
            if output.is_shutter:
                # Shutter outputs cannot be changed
                continue
            output.save()  # TODO: Batch saving - postpone eeprom activate if relevant for the Core

    def get_output_status(self, output_id):
        return self._output_states.get(output_id)

    def get_output_statuses(self):
        return self._output_states.values()

    def _refresh_output_states(self):
        for i in self._enumerate_io_modules('output'):
            state = self._master_communicator.do_command(CoreAPI.output_detail(), {'device_nr': i})
            self._process_new_output_state(i, state['status'], state['timer'], state['dimmer'])
        self._output_last_updated = time.time()

    # Shutters

    def shutter_up(self, shutter_id):
        self._master_communicator.do_basic_action(action_type=10,
                                                  action=1,
                                                  device_nr=shutter_id)

    def shutter_down(self, shutter_id):
        self._master_communicator.do_basic_action(action_type=10,
                                                  action=2,
                                                  device_nr=shutter_id)

    def shutter_stop(self, shutter_id):
        self._master_communicator.do_basic_action(action_type=10,
                                                  action=0,
                                                  device_nr=shutter_id)

    def load_shutter(self, shutter_id):  # type: (int) -> ShutterDTO
        shutter = ShutterConfiguration(shutter_id)
        shutter_dto = ShutterMapper.orm_to_dto(shutter)
        # Load information that is set on the Output(Module)Configuration
        output_module = OutputConfiguration(shutter.outputs.output_0).module
        if getattr(output_module.shutter_config, 'set_{0}_direction'.format(shutter.output_set)):
            shutter_dto.up_down_config = 0
        else:
            shutter_dto.up_down_config = 1
        return shutter_dto

    def load_shutters(self):  # type: () -> List[ShutterDTO]
        # At this moment, the system expects a given amount of Shutter modules to be physically
        # installed. However, in the Core+, this is not the case as a Shutter isn't a physical module
        # but instead a virtual layer over physical Output modules. For easy backwards compatible
        # implementation, a Shutter will map 1-to-1 to the Outputs with the same ID. This means we only need
        # to emulate such a Shutter module foreach Output module.
        shutters = []
        for shutter_id in self._enumerate_io_modules('output', amount_per_module=4):
            shutters.append(self.load_shutter(shutter_id))
        return shutters

    def save_shutters(self, shutters):  # type: (List[Tuple[ShutterDTO, List[str]]]) -> None
        # TODO: Batch saving - postpone eeprom activate if relevant for the Core
        # TODO: Atomic saving
        for shutter_dto, fields in shutters:
            # Configure shutter
            shutter = ShutterMapper.dto_to_orm(shutter_dto, fields)
            if shutter.timer_down is not None and shutter.timer_up is not None:
                # Shutter is "configured"
                shutter.outputs.output_0 = shutter.id * 2
                self._output_shutter_map[shutter.outputs.output_0] = shutter.id
                self._output_shutter_map[shutter.outputs.output_1] = shutter.id
                is_configured = True
            else:
                self._output_shutter_map.pop(shutter.outputs.output_0, None)
                self._output_shutter_map.pop(shutter.outputs.output_1, None)
                shutter.outputs.output_0 = 255 * 2
                is_configured = False
            shutter.save()
            # Mark related Outputs as "occupied by shutter"
            output_module = OutputConfiguration(shutter_dto.id * 2).module
            setattr(output_module.shutter_config, 'are_{0}_outputs'.format(shutter.output_set), not is_configured)
            setattr(output_module.shutter_config, 'set_{0}_direction'.format(shutter.output_set), shutter_dto.up_down_config == 0)
            output_module.save()

    def _refresh_shutter_states(self):
        for shutter_id in self._enumerate_io_modules('output', amount_per_module=4):
            shutter = ShutterConfiguration(shutter_id)
            if shutter.outputs.output_0 != 255 * 2:
                self._output_shutter_map[shutter.outputs.output_0] = shutter.id
                self._output_shutter_map[shutter.outputs.output_1] = shutter.id
            else:
                self._output_shutter_map.pop(shutter.outputs.output_0, None)
                self._output_shutter_map.pop(shutter.outputs.output_1, None)
            self._refresh_shutter_state(shutter_id)
        self._shutters_last_updated = time.time()

    def _refresh_shutter_state(self, shutter_id):
        shutter = ShutterConfiguration(shutter_id)
        if shutter.outputs.output_0 == 255 * 2:
            return
        output_0_on = self._output_states.get(shutter.outputs.output_0)['status'] == 1
        output_1_on = self._output_states.get(shutter.outputs.output_1)['status'] == 1
        output_module = OutputConfiguration(shutter.outputs.output_0).module
        if getattr(output_module.shutter_config, 'set_{0}_direction'.format(shutter.output_set)):
            up, down = output_1_on, output_0_on
        else:
            up, down = output_0_on, output_1_on

        if up == 1 and down == 0:
            state = ShutterEnums.State.GOING_UP
        elif down == 1 and up == 0:
            state = ShutterEnums.State.GOING_DOWN
        else:  # Both are off or - unlikely - both are on
            state = ShutterEnums.State.STOPPED

        for callback in self._event_callbacks:
            event_data = {'id': shutter_id,
                          'status': state,
                          'location': {'room_id': 255}}  # TODO: rooms
            callback(MasterEvent(event_type=MasterEvent.Types.SHUTTER_CHANGE, data=event_data))

    def shutter_group_up(self, shutter_group_id):  # type: (int) -> None
        raise NotImplementedError()  # TODO: Implement once supported by Core(+)

    def shutter_group_down(self, shutter_group_id):  # type: (int) -> None
        raise NotImplementedError()  # TODO: Implement once supported by Core(+)

    def shutter_group_stop(self, shutter_group_id):  # type: (int) -> None
        raise NotImplementedError()  # TODO: Implement once supported by Core(+)

    def load_shutter_group(self, shutter_group_id):  # type: (int) -> ShutterGroupDTO
        return ShutterGroupDTO(id=shutter_group_id)

    def load_shutter_groups(self):  # type: () -> List[ShutterGroupDTO]
        shutter_groups = []
        for i in xrange(16):
            shutter_groups.append(ShutterGroupDTO(id=i))
        return shutter_groups

    def save_shutter_groups(self, shutter_groups):  # type: (List[Tuple[ShutterGroupDTO, List[str]]]) -> None
        pass  # TODO: Implement when/if ShutterGroups get actual properties

    # Can Led functions

    def load_can_led_configurations(self, fields=None):
        # type: (Any) -> List[Dict[str,Any]]
        return []  # TODO: implement

    # Sensors

    def get_sensor_temperature(self, sensor_id):
        return self._sensor_states.get(sensor_id, {}).get('TEMPERATURE')

    def get_sensors_temperature(self):
        amount_sensor_modules = self._master_communicator.do_command(CoreAPI.general_configuration_number_of_modules(), {})['sensor']
        temperatures = []
        for sensor_id in xrange(amount_sensor_modules * 8):
            temperatures.append(self.get_sensor_temperature(sensor_id))
        return temperatures

    def get_sensor_humidity(self, sensor_id):
        return self._sensor_states.get(sensor_id, {}).get('HUMIDITY')

    def get_sensors_humidity(self):
        amount_sensor_modules = self._master_communicator.do_command(CoreAPI.general_configuration_number_of_modules(), {})['sensor']
        humidities = []
        for sensor_id in xrange(amount_sensor_modules * 8):
            humidities.append(self.get_sensor_humidity(sensor_id))
        return humidities

    def get_sensor_brightness(self, sensor_id):
        # TODO: This is a lux value and must somehow be converted to legacy percentage
        brightness = self._sensor_states.get(sensor_id, {}).get('BRIGHTNESS')
        if brightness in [None, 65535]:
            return None
        return int(float(brightness) / 65535.0 * 100)

    def get_sensors_brightness(self):
        amount_sensor_modules = self._master_communicator.do_command(CoreAPI.general_configuration_number_of_modules(), {})['sensor']
        brightnesses = []
        for sensor_id in xrange(amount_sensor_modules * 8):
            brightnesses.append(self.get_sensor_brightness(sensor_id))
        return brightnesses

    def load_sensor(self, sensor_id, fields=None):
        sensor = SensorConfiguration(sensor_id)
        data = {'id': sensor.id,
                'name': sensor.name,
                'offset': 0,
                'virtual': False,
                'room': 255}
        if fields is None:
            return data
        return {field: data[field] for field in fields}

    def load_sensors(self, fields=None):
        amount_sensor_modules = self._master_communicator.do_command(CoreAPI.general_configuration_number_of_modules(), {})['sensor']
        sensors = []
        for i in xrange(amount_sensor_modules * 8):
            sensors.append(self.load_sensor(i, fields))
        return sensors

    def save_sensors(self, sensors):
        for sensor_data in sensors:
            new_data = {'id': sensor_data['id'],
                        'name': sensor_data['name']}  # TODO: Rest of the mapping
            sensor = SensorConfiguration.deserialize(new_data)
            sensor.save()  # TODO: Batch saving - postpone eeprom activate if relevant for the Core

    def _refresh_sensor_states(self):
        amount_sensor_modules = self._master_communicator.do_command(CoreAPI.general_configuration_number_of_modules(), {})['sensor']
        for module_nr in xrange(amount_sensor_modules):
            temperature_values = self._master_communicator.do_command(CoreAPI.sensor_temperature_values(), {'module_nr': module_nr})['values']
            brightness_values = self._master_communicator.do_command(CoreAPI.sensor_brightness_values(), {'module_nr': module_nr})['values']
            humidity_values = self._master_communicator.do_command(CoreAPI.sensor_humidity_values(), {'module_nr': module_nr})['values']
            for i in xrange(8):
                sensor_id = module_nr * 8 + i
                self._sensor_states[sensor_id] = {'TEMPERATURE': temperature_values[i],
                                                  'BRIGHTNESS': brightness_values[i],
                                                  'HUMIDITY': humidity_values[i]}
        self._sensor_last_updated = time.time()

    def set_virtual_sensor(self, sensor_id, temperature, humidity, brightness):
        raise NotImplementedError()

    def add_virtual_output_module(self):
        raise NotImplementedError()

    def add_virtual_dim_module(self):
        raise NotImplementedError()

    def add_virtual_input_module(self):
        raise NotImplementedError()

    # Rooms

    def load_room_configuration(self, room_id, fields=None):
        # type: (int, Any) -> Dict[str,Any]
        return {}

    def load_room_configurations(self, fields=None):
        # type: (Any) -> List[Dict[str,Any]]
        return []

    # Generic

    def power_cycle_bus(self):
        raise NotImplementedError()

    def get_status(self):
        # TODO: implement
        return {'time': '%02d:%02d' % (0, 0),
                'date': '%02d/%02d/%d' % (0, 0, 0),
                'mode': 42,
                'version': '%d.%d.%d' % (0, 0, 1),
                'hw_version': 1}

    def reset(self):
        raise NotImplementedError()

    def cold_reset(self):
        raise NotImplementedError()

    def get_modules(self):
        # TODO: implement
        return {'outputs': [], 'inputs': [], 'shutters': [], 'can_inputs': []}

    def get_modules_information(self):
        raise NotImplementedError()

    def flash_leds(self, led_type, led_id):
        raise NotImplementedError()

    def get_backup(self):
        raise NotImplementedError()

    def restore(self, data):
        raise NotImplementedError()

    def factory_reset(self):
        raise NotImplementedError()

    def error_list(self):
        raise NotImplementedError()

    def last_success(self):
        return time.time()

    def clear_error_list(self):
        raise NotImplementedError()

    def set_status_leds(self, status):
        raise NotImplementedError()

    def do_basic_action(self, action_type, action_number):
        raise NotImplementedError()

    def do_group_action(self, group_action_id):
        raise NotImplementedError()

    def set_all_lights_off(self):
        raise NotImplementedError()

    def set_all_lights_floor_off(self, floor):
        raise NotImplementedError()

    def set_all_lights_floor_on(self, floor):
        raise NotImplementedError()

    def get_configuration_dirty_flag(self):
        return False


class MasterInputState(object):
    def __init__(self, interval=300):
        # type: (int) -> None
        self._interval = interval
        self._last_updated = 0  # type: float
        self._values = {}  # type: Dict[int,MasterInputValue]

    def get_inputs(self):
        # type: () -> List[Dict[str,Any]]
        return [x.serialize() for x in self._values.values()]

    def get_recent(self):
        # type: () -> List[int]
        sorted_inputs = sorted(self._values.values(), key=lambda x: x.changed_at)
        recent_events = [x.input_id for x in sorted_inputs
                         if x.changed_at > time.time() - 10]
        return recent_events[-5:]

    def handle_event(self, core_event):
        # type: (MasterCoreEvent) -> MasterEvent
        value = MasterInputValue.from_core_event(core_event)
        if value.input_id not in self._values:
            self._values[value.input_id] = value
        self._values[value.input_id].update(value)
        return value.master_event()

    def should_refresh(self):
        # type: () -> bool
        return self._last_updated + self._interval < time.time()

    def refresh(self, info):
        # type: (List[int]) -> List[MasterEvent]
        events = []
        for i, byte in enumerate(info):
            for j in xrange(0, 8):
                current_status = byte >> j & 0x1
                input_id = (i * 8) + j
                if input_id not in self._values:
                    self._values[input_id] = MasterInputValue(input_id, current_status)
                state = self._values[input_id]
                if state.update_status(current_status):
                    events.append(state.master_event())
        self._last_updated = time.time()
        return events


class MasterInputValue(object):
    def __init__(self, input_id, status, changed_at=0):
        # type: (int, int, float) -> None
        self.input_id = input_id
        self.status = status
        self.changed_at = changed_at

    @classmethod
    def from_core_event(cls, event):
        # type: (MasterCoreEvent) -> MasterInputValue
        status = 1 if event.data['status'] else 0
        changed_at = time.time()
        return cls(event.data['input'], status, changed_at=changed_at)

    def serialize(self):
        # type: () -> Dict[str,Any]
        return {'id': self.input_id, 'status': self.status}  # TODO: output?

    def update(self, other_value):
        # type: (MasterInputValue) -> None
        self.update_status(other_value.status)

    def update_status(self, current_status):
        # type: (int) -> bool
        is_changed = self.status != current_status
        if is_changed:
            self.status = current_status
            self.changed_at = time.time()
        return is_changed

    def master_event(self):
        # type: () -> MasterEvent
        return MasterEvent(event_type=MasterEvent.Types.INPUT_CHANGE,
                           data={'id': self.input_id,
                                 'status': bool(self.status),
                                 'location': {'room_id': 255}})  # TODO: missing room

    def __repr__(self):
        # type: () -> str
        return '<MasterInputValue {} {} {}>'.format(self.input_id, self.status, self.changed_at)
