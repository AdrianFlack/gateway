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
Tests for the passthrough module.

@author: fryckbos
"""

from __future__ import absolute_import

import time
import unittest

import xmlrunner

from ioc import SetTestMode, SetUpTestInjections
from master.classic.master_communicator import MasterCommunicator
from master.classic.passthrough import PassthroughService
from serial_test import DummyPty, SerialMock, sin, sout


class PassthroughServiceTest(unittest.TestCase):
    """ Tests for :class`PassthroughService`. """

    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def test_passthrough(self):
        """ Test the passthrough. """
        master_pty = DummyPty(['response',
                               'more response'])
        passthrough_mock = SerialMock([
                        sin("data for the passthrough"), sout("response"),
                        sin("more data"), sout("more response")])
        SetUpTestInjections(controller_serial=master_pty,
                            passthrough_serial=passthrough_mock)

        master_communicator = MasterCommunicator(init_master=False)
        master_communicator.enable_passthrough()
        master_communicator.start()

        SetUpTestInjections(master_communicator=master_communicator)

        passthrough = PassthroughService()
        passthrough.start()

        master_pty.fd.write(bytearray(b'data for the passthrough'))
        master_pty.master_wait()
        master_pty.fd.write(bytearray(b'more data'))
        master_pty.master_wait()
        time.sleep(0.2)

        self.assertEqual(33, master_communicator.get_communication_statistics()['bytes_read'])
        self.assertEqual(21, master_communicator.get_communication_statistics()['bytes_written'])

        self.assertEqual(21, passthrough_mock.bytes_read)
        self.assertEqual(33, passthrough_mock.bytes_written)

        passthrough.stop()


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='../gw-unit-reports'))
