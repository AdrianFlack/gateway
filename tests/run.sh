#!/bin/bash -e
export PYTHONPATH=$PYTHONPATH:`pwd`/../src

echo "Running master api tests"
python2 -m master_tests.master_api_tests

echo "Running master command tests"
python2 -m master_tests.master_command_tests

echo "Running master communicator tests"
python2 -m master_tests.master_communicator_tests

echo "Running outputs tests"
python2 -m master_tests.outputs_tests

echo "Running inputs tests"
python2 -m master_tests.inputs_tests

echo "Running passthrough tests"
python2 -m master_tests.passthrough_tests

echo "Running thermostats tests"
python2 -m master_tests.thermostats_tests

echo "Running eeprom controller tests"
python2 -m master_tests.eeprom_controller_tests

echo "Running eeprom extension tests"
python2 -m master_tests.eeprom_extension_tests

echo "Running users tests"
python2 -m gateway_tests.users_tests

echo "Running scheduling tests"
python2 -m gateway_tests.scheduling_tests

echo "Running power controller tests"
python2 -m power_tests.power_controller_tests

echo "Running power communicator tests"
python2 -m power_tests.power_communicator_tests

echo "Running time keeper tests"
python2 -m power_tests.time_keeper_tests

echo "Running plugin base tests"
python2 -m plugins_tests.base_tests

echo "Running plugin interfaces tests"
python2 -m plugins_tests.interfaces_tests
