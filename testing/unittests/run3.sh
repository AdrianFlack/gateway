#!/bin/bash -e

export PYTHONPATH=$PYTHONPATH:`pwd`/../../src

echo "Running master api tests"
pytest master_tests/master_api_test.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/MasterApiTest.xml

echo "Running master command tests"
pytest master_tests/master_command_test.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/MasterCommandTest.xml

#echo "Running master communicator tests"
#pytest master_tests/master_communicator_test.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/MasterCommunicatorTest.xml

echo "Running outputs tests"
pytest master_tests/outputs_test.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/MasterOutputsTest.xml

echo "Running inputs tests"
pytest master_tests/inputs_test.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/MasterInputsTest.xml

#echo "Running passthrough tests"
#pytest master_tests/passthrough_test.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/MasterPassthroughTest.xml

echo "Running eeprom controller tests"
pytest master_tests/eeprom_controller_test.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/MasterEEPROMControllerTest.xml

echo "Running eeprom extension tests"
pytest master_tests/eeprom_extension_test.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/MasterEEPROMExtensionTest.xml

echo "Running users tests"
pytest gateway_tests/users_test.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/GatewayUsersTest.xml

#echo "Running scheduling tests"
#pytest gateway_tests/scheduling_test.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/GatewaySchedulingTest.xml

echo "Running shutter tests"
pytest gateway_tests/shutter_test.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/GatewayShutterTest.xml

echo "Running power controller tests"
pytest power_tests/power_controller_test.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/PowerControllerTest.xml

echo "Running power communicator tests"
#pytest power_tests/power_communicator_test.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/PowerCommunicatorTest.xml

echo "Running time keeper tests"
pytest power_tests/time_keeper_test.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/PowerTimeKeeperTest.xml

#echo "Running plugin base tests"
#pytest plugins_tests/base_test.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/PluginsBaseTest.xml

echo "Running plugin interfaces tests"
pytest plugins_tests/interfaces_test.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/PluginsInterfacesTest.xml

#echo "Running pulse counter controller tests"
#python3 gateway_tests/pulses_test.py

#echo "Running classic controller tests"
#python3 gateway/hal/master_controller_classic_test.py

#echo "Running core controller tests"
#python3 gateway/hal/master_controller_core_test.py

echo "Running frontpanel classic controller tests"
python3 gateway/hal/frontpanel_controller_classic_test.py

echo "Running frontpanel core controller tests"
python3 gateway/hal/frontpanel_controller_core_test.py

#echo "Running observer tests"
#python3 gateway/observer_test.py

#echo "Running Core uCAN tests"
#python3 master_core_tests/ucan_communicator_test.py

#echo "Running Core memory file tests"
#python3 master_core_tests/memory_file_test.py

echo "Running Core memory types tests"
pytest master_core_tests/memory_types_test.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/CoreMemoryTypesTest.xml

#echo "Running Core api field tests"
#pytest master_core_tests/api_field_test.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/CoreAPIFieldsTest.xml

echo "running Core communicator tests"
pytest master_core_tests/core_communicator_test.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/MasterCoreCommunicatorTest.xml

echo "running Core group action tests"
pytest master_core_tests/group_action_test.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/MasterCoreGATest.xml

#echo "Running metrics tests"
#python3 gateway_tests/metrics_test.py

echo "Running thermostat tests"
pytest thermostat_tests/gateway_mapping_test.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/GatewayThermostatMappingTest.xml

echo "Running master_tool.py tests"
pytest master_tool_test.py --log-level=DEBUG --durations=2 --junit-xml ../gw-unit-reports-3/MasterToolTests.xml
