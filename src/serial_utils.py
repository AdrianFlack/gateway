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
Serial tools contains the RS485 wrapper, printable and CommunicationTimedOutException.

@author: fryckbos
"""

from __future__ import absolute_import
import struct
import fcntl
from threading import Thread
from six.moves.queue import Queue


class CommunicationTimedOutException(Exception):
    """ An exception that is raised when the master did not respond in time. """
    def __init__(self, message=None):
        Exception.__init__(self, message)


def printable(data):
    """ prints data in a human-redable way """

    if isinstance(data, list):
        byte_notation = ' '.join(['{0: >3}'.format(i) for i in data])
        string_notation = ''.join([str(chr(i)) if 32 < i <= 126 else '.' for i in data])
    elif isinstance(data, str):
        byte_notation = ' '.join(['{0: >3}'.format(c) for c in data])
        string_notation = ''.join([c if 32 < ord(c) <= 126 else '.' for c in data])

    else:
        byte_notation = ' '.join(['{0: >3}'.format(c) for c in data])
        string_notation = ''.join([str(c) if 32 < c <= 126 else '.' for c in data])
    return '{0}    {1}'.format(byte_notation, string_notation)


class RS485(object):
    """ Replicates the pyserial interface. """

    def __init__(self, serial):
        """ Initialize a rs485 connection using the serial port. """
        self.__serial = serial
        fileno = serial.fileno()
        if fileno is not None:
            serial_rs485 = struct.pack('hhhhhhhh', 3, 0, 0, 0, 0, 0, 0, 0)
            fcntl.ioctl(fileno, 0x542F, serial_rs485)

        serial.timeout = None
        self.__thread = Thread(target=self._reader,
                               name='RS485 reader')
        self.__thread.daemon = True
        self.__thread.start()
        self.read_queue = Queue()

    def write(self, data):
        """ Write data to serial port """
        self.__serial.write(data)

    def _reader(self):
        try:
            while True:
                byte = self.__serial.read(1)
                if len(byte) == 1:
                    self.read_queue.put(byte)
                size = self.__serial.inWaiting()
                if size > 0:
                    for byte in self.__serial.read(size):
                        self.read_queue.put(byte)
        except Exception as ex:
            print('Error in reader: {0}'.format(ex))
