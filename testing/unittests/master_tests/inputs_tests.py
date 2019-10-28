# Copyright (C) 2016 OpenMotics BVBA
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
""""
Tests for InputStatus.
"""

import unittest
import xmlrunner
import time

from master.inputs import InputStatus


class InputStatusTest(unittest.TestCase):
    """ Tests for InputStatus. """

    def test_add(self):
        """ Test adding data to the InputStatus. """
        inps = InputStatus(5, 300)
        inps.add_data(1)
        self.assertEquals([1], inps.get_recent())

        inps.add_data(2)
        self.assertEquals([1, 2], inps.get_recent())

        inps.add_data(3)
        self.assertEquals([1, 2, 3], inps.get_recent())

        inps.add_data(4)
        self.assertEquals([1, 2, 3, 4], inps.get_recent())

        inps.add_data(5)
        self.assertEquals([1, 2, 3, 4, 5], inps.get_recent())

        inps.add_data(6)
        self.assertEquals([2, 3, 4, 5, 6], inps.get_recent())

        inps.add_data(7)
        self.assertEquals([3, 4, 5, 6, 7], inps.get_recent())

    def test_timeout(self):
        """ Test timeout of InputStatus data. """
        inps = InputStatus(5, 1)
        inps.add_data(1)
        self.assertEquals([1], inps.get_recent())

        time.sleep(0.8)

        inps.add_data(2)
        self.assertEquals([1, 2], inps.get_recent())

        time.sleep(0.3)

        self.assertEquals([2], inps.get_recent())


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='../gw-unit-reports'))
