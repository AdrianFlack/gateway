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

from gateway.metrics_collector import MetricsCollector
from ioc import Scope, SetTestMode, SetUpTestInjections
from power.power_api import RealtimePower


class MetricsCollectorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()

    @Scope
    def setUp(self):
        self.gateway_api = mock.Mock()
        self.gateway_api.get_power_modules.return_value = [
            {'id': 10, 'address': 11, 'version': 1,
             'input0': 'foo', 'input1': 'bar', 'input2': 'baz',
             'input3': '', 'input4': '', 'input5': '', 'input6': '',
             'input7': ''}
        ]
        self.gateway_api.get_realtime_power.return_value = {}
        self.gateway_api.get_total_energy.return_value = {}
        SetUpTestInjections(gateway_api=self.gateway_api,
                            pulse_counter_controller=mock.Mock(),
                            thermostat_controller=mock.Mock(),
                            output_controller=mock.Mock(),
                            input_controller=mock.Mock(),
                            sensor_controller=mock.Mock())
        self.controller = MetricsCollector()

    def test_realtime_power_metrics(self):
        self.gateway_api.get_realtime_power.return_value = {'10': [RealtimePower(10.0, 2.1, 5.0, 3.6)]}
        with mock.patch.object(self.controller, '_enqueue_metrics') as enqueue:
            self.controller._run_power_metrics('energy')
            expected_call = mock.call(timestamp=mock.ANY,
                                      metric_type='energy',
                                      tags={'type': 'openmotics', 'id': '11.0', 'name': 'foo'},
                                      values={'current': 5.0, 'frequency': 2.1, 'power': 3.6, 'voltage': 10.0})
            assert enqueue.call_args_list == [expected_call]

    def test_total_power_metrics(self):
        self.gateway_api.get_total_energy.return_value = {'10': [[10.0, 2.1]]}
        with mock.patch.object(self.controller, '_enqueue_metrics') as enqueue:
            self.controller._run_power_metrics('energy')
            expected_call = mock.call(timestamp=mock.ANY,
                                      metric_type='energy',
                                      tags={'type': 'openmotics', 'id': '11.0', 'name': 'foo'},
                                      values={'counter_day': 10.0, 'counter_night': 2.1, 'counter': 12.1})
            assert enqueue.call_args_list == [expected_call]
