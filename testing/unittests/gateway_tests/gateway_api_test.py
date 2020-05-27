# Copyright (C) 2020 OpenMotics BV
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
from __future__ import absolute_import

import unittest

import mock

from gateway.gateway_api import GatewayApi
from ioc import SetTestMode, SetUpTestInjections
from power.power_api import P1_CONCENTRATOR, POWER_MODULE


class GatewayApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        self.power_controller = mock.Mock()
        self.p1_controller = mock.Mock()
        SetUpTestInjections(master_controller=mock.Mock(),
                            power_communicator=mock.Mock(),
                            power_controller=self.power_controller,
                            p1_controller=self.p1_controller,
                            message_client=mock.Mock(),
                            observer=mock.Mock(),
                            configuration_controller=mock.Mock())
        self.api = GatewayApi()

    def test_get_power_modules(self):
        self.power_controller.get_power_modules.return_value = {
            0: {'address': 0, 'name': 'Power', 'version': POWER_MODULE},
            1: {'address': 1, 'name': 'P1', 'version': P1_CONCENTRATOR},
        }
        result = self.api.get_power_modules()
        assert result == [
            {'address': 'E0', 'name': 'Power', 'version': 8},
            {'address': 'C1', 'name': 'P1', 'version': 1}
        ]

    def test_get_realtime_power(self):
        self.power_controller.get_power_modules.return_value = {0: {'address': 0, 'version': POWER_MODULE}}
        self.power_controller.get_module_current.return_value = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
        self.power_controller.get_module_frequency.return_value = [1.0]
        self.power_controller.get_module_power.return_value = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
        self.power_controller.get_module_voltage.return_value = [1.0]
        result = self.api.get_realtime_power()
        assert result == {
            '0': [
                [1.0, 1.0, 1.0, 1.0],
                [1.0, 1.0, 2.0, 2.0],
                [1.0, 1.0, 3.0, 3.0],
                [1.0, 1.0, 4.0, 4.0],
                [1.0, 1.0, 5.0, 5.0],
                [1.0, 1.0, 6.0, 6.0],
                [1.0, 1.0, 7.0, 7.0],
                [1.0, 1.0, 8.0, 8.0]
            ]
        }

    def test_get_realtime_power_p1(self):
        self.power_controller.get_power_modules.return_value = {0: {'address': 0, 'version': P1_CONCENTRATOR}}
        self.p1_controller.get_module_status.return_value = [0b00001011]
        self.power_controller.get_module_current.return_value = ['001  002  !42  012  ']
        self.power_controller.get_module_voltage.return_value = ['00001  002.3  !@#42  00012  ']
        self.p1_controller.get_module_delivered_power.return_value = ['000002   000003   !@#$42   000010   ']
        self.p1_controller.get_module_received_power.return_value = ['000001   000003   !@#$42   000012   ']
        result = self.api.get_realtime_power()
        assert result == {
            '0': [
                [1.0, 0.0, 3.0, 1000.0],
                [2.3, 0.0, 6.0, 0.0],
                [0.0, 0.0, 0.0, 0.0],
                [12.0, 0.0, 36.0, -2000.0],
                [0.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 0.0]
            ]
        }

    def test_get_total_energy(self):
        self.power_controller.get_power_modules.return_value = {0: {'address': 0, 'version': POWER_MODULE}}
        self.power_controller.get_module_day_energy.return_value = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
        self.power_controller.get_module_night_energy.return_value = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
        result = self.api.get_total_energy()
        assert result == {
            '0': [[1.0, 1.0],
                  [2.0, 2.0],
                  [3.0, 3.0],
                  [4.0, 4.0],
                  [5.0, 5.0],
                  [6.0, 6.0],
                  [7.0, 7.0],
                  [8.0, 8.0]]
        }

    def test_get_total_energy_p1(self):
        self.power_controller.get_power_modules.return_value = {0: {'address': 0, 'version': P1_CONCENTRATOR}}
        self.p1_controller.get_module_status.return_value = [0b00001011]
        self.power_controller.get_module_day_energy.return_value = ['000000.001    000000.002    !@#$%^&*42    000000.012    ']
        self.power_controller.get_module_night_energy.return_value = ['000000.002    000000.003    !@#$%^&*42    000000.024    ']
        result = self.api.get_total_energy()
        assert result == {
            '0': [[1, 2],
                  [2, 3],
                  [None, None],
                  [12, 24],
                  [None, None],
                  [None, None],
                  [None, None],
                  [None, None]]
        }
