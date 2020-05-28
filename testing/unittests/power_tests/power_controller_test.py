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
Tests for the power controller module.

@author: fryckbos
"""

from __future__ import absolute_import

import unittest

import mock

from ioc import SetTestMode, SetUpTestInjections
from power.power_api import P1_CONCENTRATOR, POWER_MODULE, PowerCommand
from power.power_controller import P1Controller, PowerController


class PowerControllerTest(unittest.TestCase):
    """ Tests for PowerController. """

    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def __get_controller(self):
        """ Get a PowerController using FILE. """
        SetUpTestInjections(power_db=':memory:')
        return PowerController()

    def test_empty(self):
        """ Test an empty database. """
        power_controller = self.__get_controller()
        self.assertEqual({}, power_controller.get_power_modules())
        self.assertEqual(1, power_controller.get_free_address())

        power_controller.register_power_module(1, POWER_MODULE)

        self.assertEqual({1: {'id': 1, 'address': 1, 'name': u'', 'version': 8,
                              'input0': u'', 'input1': u'', 'input2': u'', 'input3': u'',
                              'input4': u'', 'input5': u'', 'input6': u'', 'input7': u'',
                              'sensor0': 0, 'sensor1': 0, 'sensor2': 0, 'sensor3': 0,
                              'sensor4': 0, 'sensor5': 0, 'sensor6': 0, 'sensor7': 0,
                              'times0': None, 'times1': None, 'times2': None, 'times3': None,
                              'times4': None, 'times5': None, 'times6': None, 'times7': None,
                              'inverted0': 0, 'inverted1': 0, 'inverted2': 0, 'inverted3': 0,
                              'inverted4': 0, 'inverted5': 0, 'inverted6': 0, 'inverted7': 0}},
                         power_controller.get_power_modules())

        self.assertEqual(2, power_controller.get_free_address())

        power_controller.register_power_module(5, POWER_MODULE)
        self.assertEqual({1: {'id': 1, 'address': 1, 'name': u'', 'version': 8,
                              'input0': u'', 'input1': u'', 'input2': u'', 'input3': u'',
                              'input4': u'', 'input5': u'', 'input6': u'', 'input7': u'',
                              'sensor0': 0, 'sensor1': 0, 'sensor2': 0, 'sensor3': 0,
                              'sensor4': 0, 'sensor5': 0, 'sensor6': 0, 'sensor7': 0,
                              'times0': None, 'times1': None, 'times2': None, 'times3': None,
                              'times4': None, 'times5': None, 'times6': None, 'times7': None,
                              'inverted0': 0, 'inverted1': 0, 'inverted2': 0, 'inverted3': 0,
                              'inverted4': 0, 'inverted5': 0, 'inverted6': 0, 'inverted7': 0},
                          2: {'id': 2, 'address': 5, 'name': u'', 'version': 8,
                              'input0': u'', 'input1': u'', 'input2': u'', 'input3': u'',
                              'input4': u'', 'input5': u'', 'input6': u'', 'input7': u'',
                              'sensor0': 0, 'sensor1': 0, 'sensor2': 0, 'sensor3': 0,
                              'sensor4': 0, 'sensor5': 0, 'sensor6': 0, 'sensor7': 0,
                              'times0': None, 'times1': None, 'times2': None, 'times3': None,
                              'times4': None, 'times5': None, 'times6': None, 'times7': None,
                              'inverted0': 0, 'inverted1': 0, 'inverted2': 0, 'inverted3': 0,
                              'inverted4': 0, 'inverted5': 0, 'inverted6': 0, 'inverted7': 0}},
                         power_controller.get_power_modules())

        self.assertEqual(6, power_controller.get_free_address())

    def test_update(self):
        """ Test for updating the power module information. """
        power_controller = self.__get_controller()
        self.assertEqual({}, power_controller.get_power_modules())

        power_controller.register_power_module(1, POWER_MODULE)

        self.assertEqual({1: {'id': 1, 'address': 1, 'name': u'', 'version': 8,
                              'input0': u'', 'input1': u'', 'input2': u'', 'input3': u'',
                              'input4': u'', 'input5': u'', 'input6': u'', 'input7': u'',
                              'sensor0': 0, 'sensor1': 0, 'sensor2': 0, 'sensor3': 0,
                              'sensor4': 0, 'sensor5': 0, 'sensor6': 0, 'sensor7': 0,
                              'times0': None, 'times1': None, 'times2': None, 'times3': None,
                              'times4': None, 'times5': None, 'times6': None, 'times7': None,
                              'inverted0': 0, 'inverted1': 0, 'inverted2': 0, 'inverted3': 0,
                              'inverted4': 0, 'inverted5': 0, 'inverted6': 0, 'inverted7': 0}},
                         power_controller.get_power_modules())

        times = ",".join(["00:00" for _ in range(14)])

        power_controller.update_power_module({'id': 1, 'name': 'module1', 'input0': 'in0',
                                              'input1': 'in1', 'input2': 'in2', 'input3': 'in3', 'input4': 'in4',
                                              'input5': 'in5',
                                              'input6': 'in6', 'input7': 'in7', 'sensor0': 0, 'sensor1': 1,
                                              'sensor2': 2, 'sensor3': 3,
                                              'sensor4': 4, 'sensor5': 5, 'sensor6': 6, 'sensor7': 7, 'times0': times,
                                              'times1': times, 'times2': times, 'times3': times, 'times4': times,
                                              'times5': times,
                                              'times6': times, 'times7': times, 'inverted0': 0, 'inverted1': 0,
                                              'inverted2': 0,
                                              'inverted3': 0, 'inverted4': 0, 'inverted5': 0, 'inverted6': 0,
                                              'inverted7': 0})

        self.assertEqual({1: {'id': 1, 'address': 1, 'version': 8, 'name': 'module1', 'input0': 'in0',
                              'input1': 'in1', 'input2': 'in2', 'input3': 'in3', 'input4': 'in4', 'input5': 'in5',
                              'input6': 'in6', 'input7': 'in7', 'sensor0': 0, 'sensor1': 1, 'sensor2': 2, 'sensor3': 3,
                              'sensor4': 4, 'sensor5': 5, 'sensor6': 6, 'sensor7': 7, 'times0': times,
                              'times1': times, 'times2': times, 'times3': times, 'times4': times, 'times5': times,
                              'times6': times, 'times7': times, 'inverted0': 0, 'inverted1': 0, 'inverted2': 0,
                              'inverted3': 0, 'inverted4': 0, 'inverted5': 0, 'inverted6': 0, 'inverted7': 0}},
                         power_controller.get_power_modules())

    def test_module_exists(self):
        """ Test for module_exists. """
        power_controller = self.__get_controller()

        self.assertFalse(power_controller.module_exists(1))

        power_controller.register_power_module(1, POWER_MODULE)

        self.assertTrue(power_controller.module_exists(1))
        self.assertFalse(power_controller.module_exists(2))

    def test_readdress_power_module(self):
        """ Test for readdress_power_module. """
        power_controller = self.__get_controller()
        power_controller.register_power_module(1, POWER_MODULE)

        power_controller.readdress_power_module(1, 2)

        self.assertFalse(power_controller.module_exists(1))
        self.assertTrue(power_controller.module_exists(2))

        self.assertEqual({1: {'id': 1, 'address': 2, 'name': u'', 'version': 8,
                              'input0': u'', 'input1': u'', 'input2': u'', 'input3': u'',
                              'input4': u'', 'input5': u'', 'input6': u'', 'input7': u'',
                              'sensor0': 0, 'sensor1': 0, 'sensor2': 0, 'sensor3': 0,
                              'sensor4': 0, 'sensor5': 0, 'sensor6': 0, 'sensor7': 0,
                              'times0': None, 'times1': None, 'times2': None, 'times3': None,
                              'times4': None, 'times5': None, 'times6': None, 'times7': None,
                              'inverted0': 0, 'inverted1': 0, 'inverted2': 0, 'inverted3': 0,
                              'inverted4': 0, 'inverted5': 0, 'inverted6': 0, 'inverted7': 0}},
                         power_controller.get_power_modules())

    def test_get_address(self):
        """ Test for get_address. """
        power_controller = self.__get_controller()
        self.assertEqual({}, power_controller.get_power_modules())

        power_controller.register_power_module(1, POWER_MODULE)
        power_controller.readdress_power_module(1, 3)

        self.assertEqual(3, power_controller.get_address(1))


class PowerP1Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        self.power_communicator = mock.Mock()
        SetUpTestInjections(power_communicator=self.power_communicator,
                            power_db=':memory:')
        self.controller = P1Controller()

    def test_get_module_meter_electricity(self):
        with mock.patch.object(self.power_communicator, 'do_command') as cmd:
            self.controller.get_module_meter_electricity({'version': P1_CONCENTRATOR,
                                                          'address': '11.0'})
            assert cmd.call_args_list == [
                mock.call('11.0', PowerCommand('G', 'M1\x00', '', '224s', module_type='C'))
            ]

    def test_get_module_meter_gas(self):
        with mock.patch.object(self.power_communicator, 'do_command') as cmd:
            self.controller.get_module_meter_gas({'version': P1_CONCENTRATOR,
                                                          'address': '11.0'})
            assert cmd.call_args_list == [
                mock.call('11.0', PowerCommand('G', 'M2\x00', '', '224s', module_type='C'))
            ]
