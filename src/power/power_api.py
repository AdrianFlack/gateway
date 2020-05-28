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
Contains the definition of the power modules Api.
"""

from __future__ import absolute_import

from collections import namedtuple

from power.power_command import PowerCommand

RealtimePower = namedtuple('RealtimePower', ('voltage', 'frequency', 'current', 'power'))

BROADCAST_ADDRESS = 255

NIGHT = 0
DAY = 1

NORMAL_MODE = 0
ADDRESS_MODE = 1

POWER_MODULE = 8
ENERGY_MODULE = 12
P1_CONCENTRATOR = 1

NUM_PORTS = {POWER_MODULE: 8,
             ENERGY_MODULE: 12,
             P1_CONCENTRATOR: 8}

LARGEST_MODULE_TYPE = [module_type for module_type in NUM_PORTS.keys()
                       if NUM_PORTS[module_type] == max(*list(NUM_PORTS.values()))][0]


def get_general_status(version):
    """
    Get the general status of a power module.
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_MODULE:
        return PowerCommand('G', 'GST', '', 'H')
    elif version == ENERGY_MODULE:
        return PowerCommand('G', 'GST', '', 'B')
    else:
        raise ValueError("Unknown power api version")


def get_time_on(version):
    """
    Get the time the power module is on (in s)
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_MODULE or version == ENERGY_MODULE:
        return PowerCommand('G', 'TON', '', 'L')
    else:
        raise ValueError("Unknown power api version")


def get_feed_status(version):
    """
    Get the feed status of the power module (12x 0=low or 1=high)
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_MODULE:
        return PowerCommand('G', 'FST', '', '8H')
    elif version == ENERGY_MODULE:
        return PowerCommand('G', 'FST', '', '12I')
    else:
        raise ValueError("Unknown power api version")


def get_feed_counter(version):
    """
    Get the feed counter of the power module
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_MODULE or version == ENERGY_MODULE:
        return PowerCommand('G', 'FCO', '', 'H')
    else:
        raise ValueError("Unknown power api version")


def get_status_p1(version):
    """ Gets the status from a P1 concentrator """
    if version == P1_CONCENTRATOR:
        return PowerCommand('G', 'SP\x00', '', 'B', module_type='C')
    else:
        raise ValueError("Unknown power api version")


def get_meter_p1(version, type=None):
    """ Gets the meter id from a P1 concentrator """
    if version == P1_CONCENTRATOR:
        if type is None:
            raise ValueError('A type is required')
        return PowerCommand('G', 'M{0}\x00'.format(type), '', '224s', module_type='C')
    else:
        raise ValueError("Unknown power api version")


def get_voltage(version, phase=None):
    """
    Get the voltage of a power module (in V)
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    :param phase: Phase to read
    """
    if version in [POWER_MODULE, ENERGY_MODULE]:
        if phase is not None:
            raise ValueError('A phase is not supported')
        if version == POWER_MODULE:
            return PowerCommand('G', 'VOL', '', 'f')
        else:
            return PowerCommand('G', 'VOL', '', '12f')
    if version == P1_CONCENTRATOR:
        if phase is None:
            raise ValueError('A phase is required')
        return PowerCommand('G', 'V{0}\x00'.format(phase), '', '56s', module_type='C')
    else:
        raise ValueError("Unknown power api version")


def get_frequency(version):
    """
    Get the frequency of a power module (in Hz)
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_MODULE:
        return PowerCommand('G', 'FRE', '', 'f')
    elif version == ENERGY_MODULE:
        return PowerCommand('G', 'FRE', '', '12f')
    else:
        raise ValueError("Unknown power api version")


def get_current(version, phase=None):
    """
    Get the current of a power module (12x in A)
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    :param phase: Phase to read
    """
    if version in [POWER_MODULE, ENERGY_MODULE]:
        if phase is not None:
            raise ValueError('A phase is not supported')
        if version == POWER_MODULE:
            return PowerCommand('G', 'CUR', '', '8f')
        else:
            return PowerCommand('G', 'CUR', '', '12f')
    if version == P1_CONCENTRATOR:
        if phase is None:
            raise ValueError('A phase is required')
        return PowerCommand('G', 'C{0}\x00'.format(phase), '', '40s', module_type='C')
    else:
        raise ValueError("Unknown power api version")


def get_power(version):
    """
    Get the power of a power module (12x in W)
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_MODULE:
        return PowerCommand('G', 'POW', '', '8f')
    elif version == ENERGY_MODULE:
        return PowerCommand('G', 'POW', '', '12f')
    else:
        raise ValueError("Unknown power api version")


def get_delivered_power(version):
    """ Gets the delivered power of a P1 concentrator """
    if version == P1_CONCENTRATOR:
        return PowerCommand('G', 'PD\x00', '', '72s', module_type='C')
    else:
        raise ValueError("Unknown power api version")


def get_received_power(version):
    """ Gets the reveived power of a P1 concentrator """
    if version == P1_CONCENTRATOR:
        return PowerCommand('G', 'PR\x00', '', '72s', module_type='C')
    else:
        raise ValueError("Unknown power api version")


def get_normal_energy(version):
    """
    Get the total energy measured by the power module (12x in Wh)
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == ENERGY_MODULE:
        return PowerCommand('G', 'ENE', '', '12L')
    else:
        raise ValueError("Unknown power api version")


def get_day_energy(version):
    """
    Get the energy measured during the day by the power module (12x in Wh)
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_MODULE:
        return PowerCommand('G', 'EDA', '', '8L')
    elif version == ENERGY_MODULE:
        return PowerCommand('G', 'EDA', '', '12L')
    elif version == P1_CONCENTRATOR:
        return PowerCommand('G', 'c1\x00', '', '112s', module_type='C')
    else:
        raise ValueError("Unknown power api version")


def get_night_energy(version):
    """
    Get the energy measured during the night by the power module (12x in Wh)
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_MODULE:
        return PowerCommand('G', 'ENI', '', '8L')
    elif version == ENERGY_MODULE:
        return PowerCommand('G', 'ENI', '', '12L')
    elif version == P1_CONCENTRATOR:
        return PowerCommand('G', 'c2\x00', '', '112s', module_type='C')
    else:
        raise ValueError("Unknown power api version")


def set_day_night(version):
    """
    Set the power module in night (0) or day (1) mode.
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_MODULE:
        return PowerCommand('S', 'SDN', '8b', '')
    elif version == ENERGY_MODULE:
        return PowerCommand('S', 'SDN', '12b', '')
    else:
        raise ValueError("Unknown power api version")


def get_sensor_types(version):
    """
    Get the sensor types used on the power modules (8x sensor type).
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_MODULE:
        return PowerCommand('G', 'CSU', '', '8b')
    elif version == ENERGY_MODULE:
        raise ValueError("Getting sensor types is not applicable for the 12 port modules.")
    else:
        raise ValueError("Unknown power api version")


def set_sensor_types(version):
    """
    Set the sensor types used on the power modules (8x sensor type).
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_MODULE:
        return PowerCommand('S', 'CSU', '8b', '')
    elif version == ENERGY_MODULE:
        raise ValueError("Setting sensor types is not applicable for the 12 port modules.")
    else:
        raise ValueError("Unknown power api version")


def set_current_clamp_factor(version):
    """
    Sets the current clamp factor.
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_MODULE:
        raise ValueError("Setting clamp factor is not applicable for the 8 port modules.")
    elif version == ENERGY_MODULE:
        return PowerCommand('S', 'CCF', '12f', '')
    else:
        raise ValueError('Unknown power api version')


def set_current_inverse(version):
    """
    Sets the current inverse.
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_MODULE:
        raise ValueError("Setting current inverse is not applicable for the 8 port modules.")
    elif version == ENERGY_MODULE:
        return PowerCommand('S', 'SCI', '=12B', '')
    else:
        raise ValueError('Unknown power api version')


# Below are the more advanced function (12p module only)

def get_voltage_sample_time(version):
    """
    Gets a voltage sample (time - oscilloscope view)
    :param version: power api version
    """
    if version == ENERGY_MODULE:
        return PowerCommand('G', 'VST', '2b', '50f')
    elif version == POWER_MODULE:
        raise ValueError("Getting a voltage sample (time) is not applicable for the 8 port modules.")
    else:
        raise ValueError("Unknown power api version")


def get_current_sample_time(version):
    """
    Gets a current sample (time - oscilloscope view)
    :param version: power api version
    """
    if version == ENERGY_MODULE:
        return PowerCommand('G', 'CST', '2b', '50f')
    elif version == POWER_MODULE:
        raise ValueError("Getting a current sample (time) is not applicable for the 8 port modules.")
    else:
        raise ValueError("Unknown power api version")


def get_voltage_sample_frequency(version):
    """
    Gets a voltage sample (frequency)
    :param version: power api version
    """
    if version == ENERGY_MODULE:
        return PowerCommand('G', 'VSF', '2b', '40f')
    elif version == POWER_MODULE:
        raise ValueError("Getting a voltage sample (frequency) is not applicable for the 8 port modules.")
    else:
        raise ValueError("Unknown power api version")


def get_current_sample_frequency(version):
    """
    Gets a current sample (frequency)
    :param version: power api version
    """
    if version == ENERGY_MODULE:
        return PowerCommand('G', 'CSF', '2b', '40f')
    elif version == POWER_MODULE:
        raise ValueError("Getting a current sample (frequency) is not applicable for the 8 port modules.")
    else:
        raise ValueError("Unknown power api version")


def read_eeprom(version, length):
    """
    Reads data from the eeprom
    :param version: power api version
    :param length: Amount of bytes to be read - must be equal to the actual length argument
    """
    if version == ENERGY_MODULE:
        return PowerCommand('G', 'EEP', '2H', '{0}B'.format(length))
    elif version == POWER_MODULE:
        raise ValueError("Reading eeprom is not possible for the 8 port modules.")
    else:
        raise ValueError("Unknown power api version")


def write_eeprom(version, length):
    """
    Write data to the eeprom
    :param version: power api version
    :param length: Amount of bytes to be read - must be equal to the actual amount of bytes written
    """
    if version == ENERGY_MODULE:
        return PowerCommand('S', 'EEP', '1H{0}B'.format(length), '')
    elif version == POWER_MODULE:
        raise ValueError("Writing eeprom is not possible for the 8 port modules.")
    else:
        raise ValueError("Unknown power api version")


# Below are the address mode functions.

def set_addressmode(version):
    """ Set the address mode of the power module, 1 = address mode, 0 = normal mode """
    if version == P1_CONCENTRATOR:
        return PowerCommand('S', 'AGT', 'b', '', module_type='C')
    return PowerCommand('S', 'AGT', 'b', '')


def want_an_address(version):
    """ The Want An Address command, send by the power modules in address mode. """
    if version == POWER_MODULE:
        return PowerCommand('S', 'WAA', '', '')
    elif version == ENERGY_MODULE:
        return PowerCommand('S', 'WAD', '', '')
    elif version == P1_CONCENTRATOR:
        return PowerCommand('S', 'WAD', '', '', module_type='C')
    else:
        raise ValueError('Unknown power api version')


def set_address(version):
    """ Reply on want_an_address, setting a new address for the power module. """
    if version == P1_CONCENTRATOR:
        return PowerCommand('S', 'SAD', 'b', '', module_type='C')
    return PowerCommand('S', 'SAD', 'b', '')


def set_voltage():
    """ Calibrate the voltage of the power module. """
    return PowerCommand('S', 'SVO', 'f', '')


def set_current():
    """ Calibrate the voltage of the power module. """
    return PowerCommand('S', 'SCU', 'f', '')


# Below are the function to reset the kwh counters

def reset_normal_energy(version):
    """
    Reset the total energy measured by the power module.
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_MODULE:
        return PowerCommand('S', 'ENE', '9B', '')
    elif version == ENERGY_MODULE:
        return PowerCommand('S', 'ENE', 'B12L', '')
    else:
        raise ValueError("Unknown power api version")


def reset_day_energy(version):
    """
    Reset the energy measured during the day by the power module.
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_MODULE:
        return PowerCommand('S', 'EDA', '9B', '')
    elif version == ENERGY_MODULE:
        return PowerCommand('S', 'EDA', 'B12L', '')
    else:
        raise ValueError("Unknown power api version")


def reset_night_energy(version):
    """
    Reset the energy measured during the night by the power module.
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_MODULE:
        return PowerCommand('S', 'ENI', '9B', '')
    elif version == ENERGY_MODULE:
        return PowerCommand('S', 'ENI', 'B12L', '')
    else:
        raise ValueError("Unknown power api version")


# Below are the bootloader functions

def bootloader_goto(version):
    """ Go to bootloader and wait for a number of seconds (b parameter) """
    if version == P1_CONCENTRATOR:
        return PowerCommand('S', 'RES', 'B', '', module_type='C')
    return PowerCommand('S', 'BGT', 'B', '')


def bootloader_read_id():
    """ Get the device id """
    return PowerCommand('G', 'BRI', '', '8B')


def bootloader_write_code(version):
    """
    Write code
    :param version: power api version (POWER_API_8_PORTS or POWER_API_12_PORTS).
    """
    if version == POWER_MODULE:
        return PowerCommand('S', 'BWC', '195B', '')
    elif version == ENERGY_MODULE:
        return PowerCommand('S', 'BWC', '132B', '')
    else:
        raise ValueError("Unknown power api version")


def bootloader_erase_code():
    """ Erase the code on a given page. """
    return PowerCommand('S', 'BEC', 'H', '')


def bootloader_write_configuration():
    """ Write configuration """
    return PowerCommand('S', 'BWF', '24B', '')


def bootloader_jump_application():
    """ Go from bootloader to applications """
    return PowerCommand('S', 'BJA', '', '')


def get_version(version):
    """ Get the current version of the power module firmware """
    if version == P1_CONCENTRATOR:
        return PowerCommand('G', 'FVE', '', '4B', module_type='C')
    return PowerCommand('G', 'FIV', '', '16s')


# Below are the debug functions

def raw_command(mode, command, num_bytes):
    """ Create a PowerCommand for debugging purposes. """
    return PowerCommand(mode, command, '%dB' % num_bytes, None)
