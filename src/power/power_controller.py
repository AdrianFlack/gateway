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
The power controller module contains the PowerController class, which keeps track of the registered
power modules and their address.
"""

from __future__ import absolute_import

import sqlite3
from threading import Lock

from ioc import INJECTED, Inject, Injectable, Singleton
from power import power_api
from power.power_api import ENERGY_MODULE, LARGEST_MODULE_TYPE, NUM_PORTS, \
    P1_CONCENTRATOR, POWER_MODULE

if False:  # MYPY
    from typing import Any, Dict, List, Optional
    from power.power_communicator import PowerCommunicator


@Injectable.named('power_controller')
@Singleton
class PowerController(object):
    """ The PowerController keeps track of the registered power modules. """

    @Inject
    def __init__(self, power_communicator=INJECTED, power_db=INJECTED):
        # type: (PowerCommunicator, str) -> None
        """
        Constructor a new PowerController.

        :param power_db: filename of the sqlite database.
        """
        self._power_communicator = power_communicator

        self._power_schema = {'name': 'TEXT default \'\'',
                              'address': 'INTEGER',
                              'version': 'INTEGER'}
        for i in range(NUM_PORTS[LARGEST_MODULE_TYPE]):
            self._power_schema.update({'input{0}'.format(i): 'TEXT default \'\'',
                                       'sensor{0}'.format(i): 'INT default 0',
                                       'times{0}'.format(i): 'TEXT',
                                       'inverted{0}'.format(i): 'INT default 0'})

        self.__connection = sqlite3.connect(power_db,
                                            detect_types=sqlite3.PARSE_DECLTYPES,
                                            check_same_thread=False,
                                            isolation_level=None)
        self.__cursor = self.__connection.cursor()
        self.__lock = Lock()

        self.__update_schema_if_needed()  # Table creations and/or migrations

    @staticmethod
    def _power_setting_fields(amount):
        fields = []
        for i in range(amount):
            fields += ['input{0}'.format(i),
                       'sensor{0}'.format(i),
                       'times{0}'.format(i),
                       'inverted{0}'.format(i)]
        return fields

    def __update_schema_if_needed(self):
        """
        Upadtes the power_modules table schema from the 8-port power module version to the
        12-port power module version. The __create_tables above generates the 12-port version, so
        the update is only performed for legacy users that still have the old schema.
        """
        with self.__lock:
            for table, schema in {'power_modules': self._power_schema}.items():
                fields = []
                for row in self.__cursor.execute('PRAGMA table_info(\'{0}\');'.format(table)):
                    fields.append(row[1])
                if len(fields) == 0:
                    self.__cursor.execute('CREATE TABLE {0} (id INTEGER PRIMARY KEY, {1});'.format(
                        table, ', '.join(['{0} {1}'.format(key, value) for key, value in schema.items()])
                    ))
                else:
                    for field, default in schema.items():
                        if field not in fields:
                            self.__cursor.execute('ALTER TABLE {0} ADD COLUMN {1} {2};'.format(table, field, default))

    def get_module_current(self, module, phase=None):
        # type: (Dict[str,Any], Optional[int]) -> List[Any]
        # TODO return type depends on module version/phase, translate here?
        cmd = power_api.get_current(module['version'], phase=phase)
        return self._power_communicator.do_command(module['address'], cmd)

    def get_module_frequency(self, module):
        # type: (Dict[str,Any]) -> List[float]
        cmd = power_api.get_frequency(module['version'])
        return self._power_communicator.do_command(module['address'], cmd)

    def get_module_power(self, module):
        # type: (Dict[str,Any]) -> List[float]
        cmd = power_api.get_power(module['version'])
        return self._power_communicator.do_command(module['address'], cmd)

    def get_module_voltage(self, module, phase=None):
        # type: (Dict[str,Any], Optional[int]) -> List[Any]
        # TODO return type depends on module version/phase, translate here?
        cmd = power_api.get_voltage(module['version'], phase=phase)
        return self._power_communicator.do_command(module['address'], cmd)

    def get_module_day_energy(self, module):
        # type: (Dict[str,Any]) -> List[float]
        if module['version'] == P1_CONCENTRATOR:
            raise ValueError("Unknown power api version")
        else:
            cmd = power_api.get_day_energy(module['version'])
            return self._power_communicator.do_command(module['address'], cmd)

    def get_module_night_energy(self, module):
        # type: (Dict[str,Any]) -> List[float]
        if module['version'] == P1_CONCENTRATOR:
            raise ValueError("Unknown power api version")
        else:
            cmd = power_api.get_night_energy(module['version'])
            return self._power_communicator.do_command(module['address'], cmd)

    def get_power_modules(self):
        """
        Get a dict containing all power modules. The key of the dict is the id of the module,
        the value is a dict depends on the version of the power module. All versions contain 'id',
        'name', 'address', 'version', 'input0', 'input1', 'input2', 'input3', 'input4', 'input5',
        'input6', 'input7', 'times0', 'times1', 'times2', 'times3', 'times4', 'times5', 'times6',
        'times7'. For the 8-port power it also contains 'sensor0', 'sensor1', 'sensor2', 'sensor3',
        'sensor4', 'sensor5', 'sensor6', 'sensor7'. For the 12-port power module also contains
        'input8', 'input9', 'input10', 'input11', 'times8', 'times9', 'times10', 'times11'.
        """
        power_modules = {}
        fields = {}
        for version in [POWER_MODULE, ENERGY_MODULE, P1_CONCENTRATOR]:
            amount = NUM_PORTS[version]
            fields[version] = ['id', 'name', 'address', 'version'] + PowerController._power_setting_fields(amount)
        with self.__lock:
            for row in self.__cursor.execute('SELECT {0} FROM power_modules;'.format(', '.join(fields[LARGEST_MODULE_TYPE]))):
                version = row[3]
                if version not in [POWER_MODULE, ENERGY_MODULE, P1_CONCENTRATOR]:
                    raise ValueError('Unknown power api version')
                power_modules[row[0]] = dict([(field, row[fields[version].index(field)])
                                              for field in fields[version]])
            return power_modules

    def get_address(self, id):
        """ Get the address of a module when the module id is provided. """
        with self.__lock:
            for row in self.__cursor.execute('SELECT address FROM power_modules WHERE id=?;', (id,)):
                return row[0]

    def get_version(self, id):
        """ Get the version of a module when the module id is provided. """
        with self.__lock:
            for row in self.__cursor.execute('SELECT version FROM power_modules WHERE id=?;', (id,)):
                return row[0]

    def module_exists(self, address):
        """ Check if a module with a certain address exists. """
        with self.__lock:
            for row in self.__cursor.execute('SELECT count(id) FROM power_modules WHERE address=?;', (address,)):
                return row[0] > 0

    def update_power_module(self, module):
        """
        Update the name and names of the inputs of the power module.

        :param module: dict depending on the version of the power module. All versions contain 'id',
        'name', 'input0', 'input1', 'input2', 'input3', 'input4', 'input5', 'input6', 'input7',
        'times0', 'times1', 'times2', 'times3', 'times4', 'times5', 'times6', 'times7'.
        For the 8-port power it also contains 'sensor0', 'sensor1', 'sensor2', 'sensor3',
        'sensor4', 'sensor5', 'sensor6', 'sensor7'. For the 12-port power module also contains
        'input8', 'input9', 'input10', 'input11', 'times8', 'times9', 'times10', 'times11'.
        """
        version = self.get_version(module['id'])
        if version not in [POWER_MODULE, ENERGY_MODULE, P1_CONCENTRATOR]:
            raise ValueError('Unknown power api version')
        amount = NUM_PORTS[version]
        fields = ['name'] + PowerController._power_setting_fields(amount)
        with self.__lock:
            self.__cursor.execute('UPDATE power_modules SET {0} WHERE id=?'.format(
                ', '.join(['{0}=?'.format(field) for field in fields])
            ), tuple([module[field] for field in fields] + [module['id']]))

    def register_power_module(self, address, version):
        """ Register a new power module using an address. """
        with self.__lock:
            self.__cursor.execute('INSERT INTO power_modules(address, version) VALUES (?, ?);', (address, version))

    def readdress_power_module(self, old_address, new_address):
        """ Change the address of a power module. """
        with self.__lock:
            self.__cursor.execute('UPDATE power_modules SET address=? WHERE address=?;', (new_address, old_address))

    def get_free_address(self):
        """ Get a free address for a power module. """
        max_address = 0
        with self.__lock:
            for row in self.__cursor.execute('SELECT address FROM power_modules;'):
                max_address = max(max_address, row[0])
            return max_address + 1 if max_address < 255 else 1

    def close(self):
        """ Close the database connection. """
        self.__connection.close()


@Injectable.named('p1_controller')
@Singleton
class P1Controller(object):
    """ The PowerController keeps track of the registered power modules. """

    @Inject
    def __init__(self, power_communicator=INJECTED):
        # type: (PowerCommunicator) -> None
        """
        Constructor a new P1Controller.
        """
        self._power_communicator = power_communicator

    # TODO: rework get_realtime_power or call this there.
    def get_realtime(self, modules):
        # type: (Dict[str,Dict[str,Any]]) -> List[Dict[str,Any]]
        """
        Get the realtime p1 measurement values.
        """
        values = []
        for module_id, module in sorted(modules.items()):
            if module['version'] == power_api.P1_CONCENTRATOR:
                statuses = self.get_module_status(modules[module_id])
                meters = self.get_module_meter(modules[module_id], type=1)
                tariffs1 = self.get_module_injection_tariff(modules[module_id], type=1)
                tariffs2 = self.get_module_injection_tariff(modules[module_id], type=2)
                tariff_indicators = self.get_module_tariff_indicator(modules[module_id])
                timestamps = self.get_module_timestamp(modules[module_id])
                gasses = self.get_module_consumption_gas(modules[module_id])
                voltages = self.get_module_voltage(modules[module_id])
                currents = self.get_module_current(modules[module_id])

                for port_id, status in enumerate(statuses):
                    if status:
                        values.append({'module_id': module_id,
                                       'port_id': port_id,
                                       'meter': meters[port_id],
                                       'timestamp': timestamps[port_id],
                                       'gas': gasses[port_id],
                                       'tariff': {'tariff1': tariffs1[port_id],
                                                  'tariff2': tariffs2[port_id],
                                                  'indicator': tariff_indicators[port_id]},
                                       'voltage': voltages[port_id],
                                       'current': currents[port_id]})

        return values

    def get_module_status(self, module):
        # type: (Dict[str,Any]) -> List[bool]
        cmd = power_api.get_status_p1(module['version'])
        payload = self._power_communicator.do_command(module['address'], cmd)[0]

        status = []
        for port_id in range(NUM_PORTS[P1_CONCENTRATOR]):
            status.append((payload & 1 << port_id) != 0)
        return status

    def get_module_meter(self, module, type=1):
        # type: (Dict[str,Any], int) -> List[str]
        """
        Request meter id for all meters and parse repsonse.
        """
        cmd = power_api.get_meter_p1(module['version'], type=type)
        payload = self._power_communicator.do_command(module['address'], cmd)[0]

        meters = []
        for port_id in range(NUM_PORTS[P1_CONCENTRATOR]):
            meters.append(payload[port_id * 28:(port_id + 1) * 28])
        return meters

    def get_module_timestamp(self, module):
        # type: (Dict[str,Any]) -> List[float]
        """
        Request timestamps for all meters and parse repsonse.
        """
        cmd = power_api.get_timestamp_p1(module['version'])
        payload = self._power_communicator.do_command(module['address'], cmd)[0]

        timestamps = []
        for port_id in range(NUM_PORTS[P1_CONCENTRATOR]):
            try:
                timestamps.append(float(payload[port_id * 13:(port_id + 1) * 13][:12]))
            except ValueError:
                timestamps.append(0.0)
        return timestamps

    def get_module_consumption_gas(self, module):
        # type: (Dict[str,Any]) -> List[float]
        """
        Request gas consumptions for all meters and parse repsonse.
        """
        cmd = power_api.get_consumption_gas_p1(module['version'])
        payload = self._power_communicator.do_command(module['address'], cmd)[0]

        consumptions = []
        for port_id in range(NUM_PORTS[P1_CONCENTRATOR]):
            try:
                consumptions.append(float(payload[port_id * 12:(port_id + 1) * 12][:9]))
            except ValueError:
                consumptions.append(0.0)
        return consumptions

    def get_module_injection_tariff(self, module, type=None):
        # type: (Dict[str,Any], int) -> List[float]
        """
        Request consumption tariff for all meters and parse repsonse.
        """
        cmd = power_api.get_injection_tariff_p1(module['version'], type=type)
        payload = self._power_communicator.do_command(module['address'], cmd)[0]

        consumptions = []
        for port_id in range(NUM_PORTS[P1_CONCENTRATOR]):
            try:
                consumptions.append(float(payload[port_id * 14:(port_id + 1) * 14][:10]))
            except ValueError:
                consumptions.append(0.0)
        return consumptions

    def get_module_tariff_indicator(self, module):
        # type: (Dict[str,Any]) -> List[float]
        """
        Request tariff indicator for all meters and parse repsonse.
        """
        cmd = power_api.get_tariff_indicator_p1(module['version'])
        payload = self._power_communicator.do_command(module['address'], cmd)[0]

        consumptions = []
        for port_id in range(NUM_PORTS[P1_CONCENTRATOR]):
            try:
                consumptions.append(float(payload[port_id * 4:(port_id + 1) * 4]))
            except ValueError:
                consumptions.append(0.0)
        return consumptions

    def get_module_current(self, module):
        # type: (Dict[str,Any]) -> List[Dict[str,float]]
        """
        Request phase voltages for all meters and parse repsonse.
        """
        payloads = {}
        for i in range(1, 4):
            cmd = power_api.get_current(module['version'], phase=i)
            payloads['phase{}'.format(i)] = self._power_communicator.do_command(module['address'], cmd)[0]

        currents = []
        for port_id in range(NUM_PORTS[P1_CONCENTRATOR]):
            phases = {}
            for phase, payload in payloads.items():
                try:
                    phases[phase] = float(payload[port_id * 5:(port_id + 1) * 6][:3])
                except ValueError:
                    phases[phase] = 0.0
            currents.append(phases)
        return currents

    def get_module_voltage(self, module):
        # type: (Dict[str,Any]) -> List[Dict[str,float]]
        """
        Request phase voltages for all meters and parse repsonse.
        """
        payloads = {}
        for i in range(1, 4):
            cmd = power_api.get_voltage(module['version'], phase=i)
            payloads['phase{}'.format(i)] = self._power_communicator.do_command(module['address'], cmd)[0]

        voltages = []
        for port_id in range(NUM_PORTS[P1_CONCENTRATOR]):
            phases = {}
            for phase, payload in payloads.items():
                try:
                    phases[phase] = float(payload[port_id * 7:(port_id + 1) * 7][:5])
                except ValueError:
                    phases[phase] = 0.0
            voltages.append(phases)
        return voltages

    def get_module_delivered_power(self, module):
        # type: (Dict[str,Any]) -> List[float]
        cmd = power_api.get_delivered_power(module['version'])
        payload = self._power_communicator.do_command(module['address'], cmd)[0]

        delivered = []
        for port_id in range(NUM_PORTS[P1_CONCENTRATOR]):
            try:
                delivered.append(float(payload[port_id * 9:(port_id + 1) * 9][:6]))
            except ValueError:
                delivered.append(0.0)
        return delivered

    def get_module_received_power(self, module):
        # type: (Dict[str,Any]) -> List[float]
        cmd = power_api.get_received_power(module['version'])
        payload = self._power_communicator.do_command(module['address'], cmd)[0]

        received = []
        for port_id in range(NUM_PORTS[P1_CONCENTRATOR]):
            try:
                received.append(float(payload[port_id * 9:(port_id + 1) * 9][:6]))
            except ValueError:
                received.append(0.0)
        return received

    def get_module_day_energy(self, module):
        # type: (Dict[str,Any]) -> List[float]
        cmd = power_api.get_day_energy(module['version'])
        payload = self._power_communicator.do_command(module['address'], cmd)[0]

        energy = []
        for port_id in range(NUM_PORTS[P1_CONCENTRATOR]):
            try:
                energy.append(float(payload[port_id * 14:(port_id + 1) * 14][:10]))
            except ValueError:
                energy.append(0.0)
        return energy

    def get_module_night_energy(self, module):
        # type: (Dict[str,Any]) -> List[float]
        cmd = power_api.get_night_energy(module['version'])
        payload = self._power_communicator.do_command(module['address'], cmd)[0]

        energy = []
        for port_id in range(NUM_PORTS[P1_CONCENTRATOR]):
            try:
                energy.append(float(payload[port_id * 14:(port_id + 1) * 14][:10]))
            except ValueError:
                energy.append(0.0)
        return energy
