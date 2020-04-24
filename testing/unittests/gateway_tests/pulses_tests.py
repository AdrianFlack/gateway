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
Tests for the pulses module.

@author: fryckbos
"""

from __future__ import absolute_import
import unittest
import xmlrunner
import os
from ioc import SetTestMode, SetUpTestInjections
from master.classic.master_communicator import MasterCommunicator
from gateway.pulses import PulseCounterController
import master.classic.master_api as master_api
from master_tests.eeprom_controller_tests import get_eeprom_controller_dummy
from serial_tests import DummyPty


class PulseCounterControllerTest(unittest.TestCase):
    """ Tests for PulseCounterController. """

    FILE = 'test.db'

    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):  # pylint: disable=C0103
        """ Run before each test. """
        if os.path.exists(PulseCounterControllerTest.FILE):
            os.remove(PulseCounterControllerTest.FILE)
        self.maxDiff = None

    def tearDown(self):  # pylint: disable=C0103
        """ Run after each test. """
        if os.path.exists(PulseCounterControllerTest.FILE):
            os.remove(PulseCounterControllerTest.FILE)

    @staticmethod
    def _get_controller(master_communicator):
        """ Get a PulseCounterController using FILE. """
        banks = []
        for i in range(255):
            banks.append("\xff" * 256)

        eeprom_controller = get_eeprom_controller_dummy(banks)
        SetUpTestInjections(pulse_db=PulseCounterControllerTest.FILE,
                            master_communicator=master_communicator,
                            eeprom_controller=eeprom_controller)
        return PulseCounterController()

    def test_pulse_counter_up_down(self):
        """ Test adding and removing pulse counters. """
        controller = self._get_controller(None)

        # Only master pulse counters
        controller.set_pulse_counter_amount(24)
        self.assertEqual(24, controller.get_pulse_counter_amount())

        # Add virtual pulse counters
        controller.set_pulse_counter_amount(28)
        self.assertEqual(28, controller.get_pulse_counter_amount())

        # Add virtual pulse counter
        controller.set_pulse_counter_amount(29)
        self.assertEqual(29, controller.get_pulse_counter_amount())

        # Remove virtual pulse counter
        controller.set_pulse_counter_amount(28)
        self.assertEqual(28, controller.get_pulse_counter_amount())

        # Set virtual pulse counters to 0
        controller.set_pulse_counter_amount(24)
        self.assertEqual(24, controller.get_pulse_counter_amount())

        # Set the number of pulse counters to low
        try:
            controller.set_pulse_counter_amount(23)
            self.fail('Exception should have been thrown')
        except ValueError as e:
            self.assertEqual('Amount should be 24 or more', str(e))

    def test_pulse_counter_status(self):
        action = master_api.pulse_list()

        in_fields = {}
        out_fields = {'pv0': 0, 'pv1': 1, 'pv2': 2, 'pv3': 3, 'pv4': 4, 'pv5': 5, 'pv6': 6, 'pv7': 7,
                      'pv8': 8, 'pv9': 9, 'pv10': 10, 'pv11': 11, 'pv12': 12, 'pv13': 13, 'pv14': 14,
                      'pv15': 15, 'pv16': 16, 'pv17': 17, 'pv18': 18, 'pv19': 19, 'pv20': 20, 'pv21': 21,
                      'pv22': 22, 'pv23': 23, 'crc': [67, 1, 20]}

        pty = DummyPty([action.create_input(1, in_fields)])
        SetUpTestInjections(controller_serial=pty)

        master_communicator = MasterCommunicator(init_master=False)
        master_communicator.start()

        pty.master_reply(action.create_output(1, out_fields))
        controller = self._get_controller(master_communicator)
        controller.set_pulse_counter_amount(26)
        controller.set_pulse_counter_status(24, 123)
        controller.set_pulse_counter_status(25, 456)

        status = controller.get_pulse_counter_status()
        self.assertEqual(list(range(0, 24)) + [123, 456], status)

        # Set pulse counter for unexisting pulse counter
        try:
            controller.set_pulse_counter_status(26, 789)
            self.fail('Exception should have been thrown')
        except ValueError as e:
            self.assertEqual('Could not find pulse counter 26', str(e))

        # Set pulse counter for physical pulse counter
        try:
            controller.set_pulse_counter_status(23, 789)
            self.fail('Exception should have been thrown')
        except ValueError as e:
            self.assertEqual('Cannot set pulse counter status for 23 (should be > 23)', str(e))

    def test_config(self):
        controller = self._get_controller(None)

        controller.set_pulse_counter_amount(26)
        controller.set_configurations([
            {'id': 1, 'name': 'Water', 'input': 10, 'room': 1},
            {'id': 4, 'name': 'Gas', 'input': 11, 'room': 2},
            {'id': 25, 'name': 'Electricity', 'input': -1, 'room': 3, 'persistent': True}
        ])
        configs = controller.get_configurations()

        self.assertEqual([{'input': 255, 'room': 255, 'id': 0, 'name': '', 'persistent': False},
                          {'input': 10, 'room': 1, 'id': 1, 'name': 'Water', 'persistent': False},
                          {'input': 255, 'room': 255, 'id': 2, 'name': '', 'persistent': False},
                          {'input': 255, 'room': 255, 'id': 3, 'name': '', 'persistent': False},
                          {'input': 11, 'room': 2, 'id': 4, 'name': 'Gas', 'persistent': False},
                          {'input': 255, 'room': 255, 'id': 5, 'name': '', 'persistent': False},
                          {'input': 255, 'room': 255, 'id': 6, 'name': '', 'persistent': False},
                          {'input': 255, 'room': 255, 'id': 7, 'name': '', 'persistent': False},
                          {'input': 255, 'room': 255, 'id': 8, 'name': '', 'persistent': False},
                          {'input': 255, 'room': 255, 'id': 9, 'name': '', 'persistent': False},
                          {'input': 255, 'room': 255, 'id': 10, 'name': '', 'persistent': False},
                          {'input': 255, 'room': 255, 'id': 11, 'name': '', 'persistent': False},
                          {'input': 255, 'room': 255, 'id': 12, 'name': '', 'persistent': False},
                          {'input': 255, 'room': 255, 'id': 13, 'name': '', 'persistent': False},
                          {'input': 255, 'room': 255, 'id': 14, 'name': '', 'persistent': False},
                          {'input': 255, 'room': 255, 'id': 15, 'name': '', 'persistent': False},
                          {'input': 255, 'room': 255, 'id': 16, 'name': '', 'persistent': False},
                          {'input': 255, 'room': 255, 'id': 17, 'name': '', 'persistent': False},
                          {'input': 255, 'room': 255, 'id': 18, 'name': '', 'persistent': False},
                          {'input': 255, 'room': 255, 'id': 19, 'name': '', 'persistent': False},
                          {'input': 255, 'room': 255, 'id': 20, 'name': '', 'persistent': False},
                          {'input': 255, 'room': 255, 'id': 21, 'name': '', 'persistent': False},
                          {'input': 255, 'room': 255, 'id': 22, 'name': '', 'persistent': False},
                          {'input': 255, 'room': 255, 'id': 23, 'name': '', 'persistent': False},
                          {'input': -1, 'room': 255, 'id': 24, 'name': '', 'persistent': False},
                          {'input': -1, 'room': 3, 'id': 25, 'name': 'Electricity', 'persistent': True}], configs)

        # Try to set input on virtual pulse counter
        try:
            controller.set_configuration({'id': 25, 'name': 'Electricity', 'input': 22, 'room': 3})
            self.fail('Exception should have been thrown')
        except ValueError as e:
            self.assertEqual('Virtual pulse counter 25 can only have input -1', str(e))

        # Get configuration for existing master pulse counter
        self.assertEqual({'input': 10, 'room': 1, 'id': 1, 'name': 'Water', 'persistent': False}, controller.get_configuration(1))

        # Get configuration for existing virtual pulse counter
        self.assertEqual({'input': -1, 'room': 3, 'id': 25, 'name': 'Electricity', 'persistent': True}, controller.get_configuration(25))

        # Get configuration for unexisting pulse counter
        try:
            controller.set_configuration({'id': 26, 'name': 'Electricity', 'input': -1, 'room': 3})
            self.fail('Exception should have been thrown')
        except ValueError as e:
            self.assertEqual('Could not find pulse counter 26', str(e))

        # Set configuration for unexisting pulse counter
        try:
            controller.get_configuration(26)
            self.fail('Exception should have been thrown')
        except ValueError as e:
            self.assertEqual('Could not find pulse counter 26', str(e))


if __name__ == '__main__':
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='../gw-unit-reports'))
