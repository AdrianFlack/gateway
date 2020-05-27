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


class GatewayApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        self.power_controller = mock.Mock()
        self.power_communicator = mock.Mock()
        SetUpTestInjections(master_controller=mock.Mock(),
                            power_communicator=self.power_communicator,
                            power_controller=self.power_controller,
                            message_client=mock.Mock(),
                            observer=mock.Mock(),
                            configuration_controller=mock.Mock())
        self.api = GatewayApi()

    def test_get_realtime_power(self):
        def do_command(add, cmd):
            if cmd.type == 'VOL':
                return [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
            elif cmd.type == 'CUR':
                return [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
            elif cmd.type == 'POW':
                return [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
            else:
                return [1.0]

        self.power_controller.get_power_modules.return_value = {0: {'address': 0, 'version': 8}}
        with mock.patch.object(self.power_communicator, 'do_command',
                               side_effect=do_command) as cmd:
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
            cmd.assert_called()
