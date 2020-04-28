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
The maintenance module contains the MaintenanceService class.
"""
from __future__ import absolute_import

# TODO: This needs to be moved to a general `master` folder with `classic` and `core` subfolders

class InMaintenanceModeException(Exception):
    pass


class MaintenanceCommunicator(object):

    def start(self):
        raise NotImplementedError()

    def stop(self):
        raise NotImplementedError()

    def set_receiver(self, callback):
        raise NotImplementedError()

    def set_deactivated(self, callback):
        raise NotImplementedError()

    def is_active(self):
        raise NotImplementedError()

    def activate(self):
        raise NotImplementedError()

    def deactivate(self, join=True):
        raise NotImplementedError()

    def write(self, message):
        raise NotImplementedError()
