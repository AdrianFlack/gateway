#!/bin/bash
export PYTHONPATH=$PYTHONPATH:`pwd`/../../src

echo "Running master api tests"
pytest master_tests/master_api_tests.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/MasterApiTest.xml

echo "Running master command tests"
pytest master_tests/master_command_tests.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/MasterCommandTest.xml

echo "Running master communicator tests"
#pytest master_tests/master_communicator_tests.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/MasterCommunicatorTest.xml

echo "Running outputs tests"
pytest master_tests/outputs_tests.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/MasterOutputsTest.xml

echo "Running inputs tests"
pytest master_tests/inputs_tests.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/MasterInputsTest.xml

echo "Running passthrough tests"
#pytest master_tests/passthrough_tests.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/MasterPassthroughTest.xml

echo "Running eeprom controller tests"
pytest master_tests/eeprom_controller_tests.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/MasterEEPROMControllerTest.xml
echo "Running eeprom extension tests"
pytest master_tests/eeprom_extension_tests.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/MasterEEPROMExtensionTest.xml

echo "Running users tests"
#pytest gateway_tests/users_tests.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/GatewayUsersTest.xml

echo "Running scheduling tests"
pytest gateway_tests/scheduling_tests.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/GatewaySchedulingTest.xml

echo "Running shutter tests"
pytest gateway_tests/shutter_tests.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/GatewayShutterTest.xml

echo "Running power controller tests"
pytest power_tests/power_controller_tests.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/PowerControllerTest.xml

echo "Running power communicator tests"
#pytest power_tests/power_communicator_tests.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/PowerCommunicatorTest.xml

echo "Running time keeper tests"
pytest power_tests/time_keeper_tests.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/PowerTimeKeeperTest.xml

echo "Running plugin base tests"
pytest plugins_tests/base_tests.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/PluginsBaseTest.xml

echo "Running plugin interfaces tests"
pytest plugins_tests/interfaces_tests.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/PluginsInterfacesTest.xml

echo "Running pulse counter controller tests"
#python3 gateway_tests/pulses_tests.py

echo "Running classic controller tests"
python3 gateway/hal/master_controller_classic_test.py

echo "Running core controller tests"
python3 gateway/hal/master_controller_core_test.py

echo "Running observer tests"
python3 gateway/observer_test.py

echo "Running Core uCAN tests"
#python3 master_core_tests/ucan_communicator_tests.py

echo "Running Core memory file tests"
python3 master_core_tests/memory_file_tests.py

echo "Running Core api field tests"
#python3 master_core_tests/api_field_tests.py

echo "running Core communicator tests"
pytest master_core_tests/core_communicator_tests.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/MasterCoreCommunicator.xml

echo "Running metrics tests"
python3 gateway_tests/metrics_tests.py
