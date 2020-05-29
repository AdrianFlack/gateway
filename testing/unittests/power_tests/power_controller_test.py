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
        SetUpTestInjections(power_communicator=mock.Mock(),
                            power_db=':memory:')
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

    def test_get_module_status(self):
        payload = 0b00001011
        with mock.patch.object(self.power_communicator, 'do_command',
                               return_value=[payload]) as cmd:
            status = self.controller.get_module_status({'version': P1_CONCENTRATOR,
                                                       'address': '11.0'})
            assert status == [
                True, True, False, True,
                False, False, False, False
            ]
            assert cmd.call_args_list == [
                mock.call('11.0', PowerCommand('G', 'SP\x00', '', 'B', module_type='C'))
            ]

    def test_get_module_meter(self):
        # TODO confirm this is correct
        payload = '11111111111111111111111111112222222222222222222222222222                            4444444444444444444444444444'
        with mock.patch.object(self.power_communicator, 'do_command',
                               return_value=[payload]) as cmd:
            meters = self.controller.get_module_meter({'version': P1_CONCENTRATOR,
                                                       'address': '11.0'},
                                                      type=1)
            assert meters == [
                '1111111111111111111111111111',
                '2222222222222222222222222222',
                '                            ',
                '4444444444444444444444444444',
                '', '', '', '',
            ]
            assert cmd.call_args_list == [
                mock.call('11.0', PowerCommand('G', 'M1\x00', '', '224s', module_type='C'))
            ]

    def test_get_module_current(self):
        payload = '001  002  !42  012  '
        with mock.patch.object(self.power_communicator, 'do_command',
                               return_value=[payload]) as cmd:
            voltages = self.controller.get_module_current({'version': P1_CONCENTRATOR,
                                                           'address': '11.0'})
            assert voltages == [
                {'phase1': 1.0, 'phase2': 1.0, 'phase3': 1.0},
                {'phase1': 2.0, 'phase2': 2.0, 'phase3': 2.0},
                {'phase1': 0.0, 'phase2': 0.0, 'phase3': 0.0},
                {'phase1': 12.0, 'phase2': 12.0, 'phase3': 12.0},
                {'phase1': 0.0, 'phase2': 0.0, 'phase3': 0.0},
                {'phase1': 0.0, 'phase2': 0.0, 'phase3': 0.0},
                {'phase1': 0.0, 'phase2': 0.0, 'phase3': 0.0},
                {'phase1': 0.0, 'phase2': 0.0, 'phase3': 0.0}
            ]
            self.assertIn(mock.call('11.0', PowerCommand('G', 'C1\x00', '', '40s', module_type='C')),
                          cmd.call_args_list)
            self.assertIn(mock.call('11.0', PowerCommand('G', 'C2\x00', '', '40s', module_type='C')),
                          cmd.call_args_list)
            self.assertIn(mock.call('11.0', PowerCommand('G', 'C3\x00', '', '40s', module_type='C')),
                          cmd.call_args_list)

    def test_get_module_voltage(self):
        payload = '00001  002.3  !@#42  00012  '
        with mock.patch.object(self.power_communicator, 'do_command',
                               return_value=[payload]) as cmd:
            voltages = self.controller.get_module_voltage({'version': P1_CONCENTRATOR,
                                                           'address': '11.0'})
            assert voltages == [
                {'phase1': 1.0, 'phase2': 1.0, 'phase3': 1.0},
                {'phase1': 2.3, 'phase2': 2.3, 'phase3': 2.3},
                {'phase1': 0.0, 'phase2': 0.0, 'phase3': 0.0},
                {'phase1': 12.0, 'phase2': 12.0, 'phase3': 12.0},
                {'phase1': 0.0, 'phase2': 0.0, 'phase3': 0.0},
                {'phase1': 0.0, 'phase2': 0.0, 'phase3': 0.0},
                {'phase1': 0.0, 'phase2': 0.0, 'phase3': 0.0},
                {'phase1': 0.0, 'phase2': 0.0, 'phase3': 0.0}
            ]
            self.assertIn(mock.call('11.0', PowerCommand('G', 'V1\x00', '', '56s', module_type='C')),
                          cmd.call_args_list)
            self.assertIn(mock.call('11.0', PowerCommand('G', 'V2\x00', '', '56s', module_type='C')),
                          cmd.call_args_list)
            self.assertIn(mock.call('11.0', PowerCommand('G', 'V3\x00', '', '56s', module_type='C')),
                          cmd.call_args_list)

    def test_get_module_delivered_power(self):
        payload = '000001   000002   !@#$42   000012   '
        with mock.patch.object(self.power_communicator, 'do_command',
                               return_value=[payload]) as cmd:
            delivered = self.controller.get_module_delivered_power({'version': P1_CONCENTRATOR,
                                                                    'address': '11.0'})
            assert delivered == [1.0, 2.0, 0.0, 12.0, 0.0, 0.0, 0.0, 0.0]
            assert cmd.call_args_list == [
                mock.call('11.0', PowerCommand('G', 'PD\x00', '', '72s', module_type='C')),
            ]

    def test_get_module_received_power(self):
        payload = '000001   000002   !@#$42   000012   '
        with mock.patch.object(self.power_communicator, 'do_command',
                               return_value=[payload]) as cmd:
            received = self.controller.get_module_received_power({'version': P1_CONCENTRATOR,
                                                                  'address': '11.0'})
            assert received == [1.0, 2.0, 0.0, 12.0, 0.0, 0.0, 0.0, 0.0]
            assert cmd.call_args_list == [
                mock.call('11.0', PowerCommand('G', 'PR\x00', '', '72s', module_type='C')),
            ]

    def test_get_module_day_energy(self):
        payload = '000000.001    000000.002    !@#$%^&*42    000000.012    '
        with mock.patch.object(self.power_communicator, 'do_command',
                               return_value=[payload]) as cmd:
            received = self.controller.get_module_day_energy({'version': P1_CONCENTRATOR,
                                                              'address': '11.0'})
            assert received == [0.001, 0.002, 0.0, 0.012, 0.0, 0.0, 0.0, 0.0]
            assert cmd.call_args_list == [
                mock.call('11.0', PowerCommand('G', 'c1\x00', '', '112s', module_type='C')),
            ]

    def test_get_module_night_energy(self):
        payload = '000000.001    000000.002    !@#$%^&*42    000000.012    '
        with mock.patch.object(self.power_communicator, 'do_command',
                               return_value=[payload]) as cmd:
            received = self.controller.get_module_night_energy({'version': P1_CONCENTRATOR,
                                                                'address': '11.0'})
            assert received == [0.001, 0.002, 0.0, 0.012, 0.0, 0.0, 0.0, 0.0]
            assert cmd.call_args_list == [
                mock.call('11.0', PowerCommand('G', 'c2\x00', '', '112s', module_type='C')),
            ]
