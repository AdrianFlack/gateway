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
This module contains logic to handle shutters with their state/position
"""
from __future__ import absolute_import
import logging
import time
from threading import Lock
from ioc import Injectable, Inject, INJECTED, Singleton
from toolbox import Toolbox
from gateway.base_controller import BaseController, SyncStructure
from gateway.hal.master_event import MasterEvent
from gateway.enums import ShutterEnums
from gateway.events import GatewayEvent
from gateway.dto import ShutterDTO, ShutterGroupDTO
from gateway.models import ShutterGroup, Shutter, Room

if False:  # MYPY
    from typing import List, Dict, Optional, Tuple

logger = logging.getLogger('openmotics')


@Injectable.named('shutter_controller')
@Singleton
class ShutterController(BaseController):
    """
    Controls everything related to shutters.

    Important assumptions:
    * A shutter can go UP and go DOWN
    * A shutter that is UP is considered open and has a position of 0
    * A shutter that is DOWN is considered closed and has a position of `steps`

    # TODO: The states OPEN and CLOSED make more sense but is a reasonable heavy change at this moment. To be updated if/when a new Gateway API is introduced
    """

    SYNC_STRUCTURES = [SyncStructure(Shutter, 'shutter'),
                       SyncStructure(ShutterGroup, 'shutter_group')]
    DIRECTION_STATE_MAP = {ShutterEnums.Direction.UP: ShutterEnums.State.GOING_UP,
                           ShutterEnums.Direction.DOWN: ShutterEnums.State.GOING_DOWN,
                           ShutterEnums.Direction.STOP: ShutterEnums.State.STOPPED}
    DIRECTION_END_STATE_MAP = {ShutterEnums.Direction.UP: ShutterEnums.State.UP,
                               ShutterEnums.Direction.DOWN: ShutterEnums.State.DOWN,
                               ShutterEnums.Direction.STOP: ShutterEnums.State.STOPPED}
    STATE_DIRECTION_MAP = {ShutterEnums.State.GOING_UP: ShutterEnums.Direction.UP,
                           ShutterEnums.State.GOING_DOWN: ShutterEnums.Direction.DOWN,
                           ShutterEnums.State.STOPPED: ShutterEnums.Direction.STOP}

    @Inject
    def __init__(self, master_controller=INJECTED, verbose=False):
        super(ShutterController, self).__init__(master_controller)

        self._shutters = {}  # type: Dict[int, ShutterDTO]
        self._actual_positions = {}
        self._desired_positions = {}
        self._directions = {}
        self._states = {}

        self._event_subscriptions = []

        self._verbose = verbose
        self._config_lock = Lock()

    def _log(self, message):
        if self._verbose:
            logger.info('ShutterController: {0}'.format(message))

    # Update internal shutter configuration cache

    def _handle_master_event(self, event):  # type: (MasterEvent) -> None
        super(ShutterController, self)._handle_master_event(event)
        if event.type == MasterEvent.Types.EEPROM_CHANGE:
            self.update_config(self.load_shutters())
        if event.type == MasterEvent.Types.SHUTTER_CHANGE:
            self._report_shutter_state(event.data['id'], event.data['status'])

    def update_config(self, config):  # type: (List[ShutterDTO]) -> None
        with self._config_lock:
            shutter_ids = []
            for shutter_dto in config:
                shutter_id = shutter_dto.id
                shutter_ids.append(shutter_id)
                if shutter_dto != self._shutters.get(shutter_id):
                    self._shutters[shutter_id] = shutter_dto
                    self._states[shutter_id] = [0, ShutterEnums.State.STOPPED]
                    self._actual_positions[shutter_id] = None
                    self._desired_positions[shutter_id] = None
                    self._directions[shutter_id] = ShutterEnums.Direction.STOP

            for shutter_id in list(self._shutters):
                if shutter_id not in shutter_ids:
                    del self._shutters[shutter_id]
                    del self._states[shutter_id]
                    del self._actual_positions[shutter_id]
                    del self._desired_positions[shutter_id]
                    del self._directions[shutter_id]

    def subscribe_events(self, callback):
        self._event_subscriptions.append(callback)

    # Allow shutter positions to be reported

    def report_shutter_position(self, shutter_id, position, direction=None):
        self._log('Shutter {0} reports position {1}'.format(shutter_id, position))
        # Fetch and validate information
        shutter = self._get_shutter(shutter_id)
        steps = ShutterController._get_steps(shutter)
        ShutterController._validate_position(shutter_id, position, steps)

        # Store new position
        self._actual_positions[shutter_id] = position

        # Update the direction and report if changed
        expected_direction = self._directions[shutter_id]
        if direction is not None and expected_direction != direction:
            # We received a more accurate direction
            self._log('Shutter {0} report direction change to {1}'.format(shutter_id, direction))
            self._report_shutter_state(shutter_id, ShutterController.DIRECTION_STATE_MAP[direction])

        direction = self._directions[shutter_id]
        desired_position = self._desired_positions[shutter_id]
        if desired_position is None:
            return
        if ShutterController._is_position_reached(direction, desired_position, position, stopped=True):
            self._log('Shutter {0} reported position is desired position: Stopping'.format(shutter_id))
            self.shutter_stop(shutter_id)

    # Configure shutters

    def load_shutter(self, shutter_id):  # type: (int) -> ShutterDTO
        shutter = Shutter.get(number=shutter_id)  # type: Shutter
        shutter_dto = self._master_controller.load_shutter(shutter_id=shutter.number)
        shutter_dto.room = shutter.room.number if shutter.room is not None else None
        return shutter_dto

    def load_shutters(self):  # type: () -> List[ShutterDTO]
        shutter_dtos = []
        for shutter in Shutter.select():
            shutter_dto = self._master_controller.load_shutter(shutter_id=shutter.number)
            shutter_dto.room = shutter.room.number if shutter.room is not None else None
            shutter_dtos.append(shutter_dto)
        return shutter_dtos

    def save_shutters(self, shutters):  # type: (List[Tuple[ShutterDTO, List[str]]]) -> None
        shutters_to_save = []
        for shutter_dto, fields in shutters:
            shutter = Shutter.get_or_none(number=shutter_dto.id)  # type: Shutter
            if shutter is None:
                logger.info('Ignored saving non-existing Shutter {0}'.format(shutter_dto.id))
            if 'room' in fields:
                if shutter_dto.room is None:
                    shutter.room = None
                elif 0 <= shutter_dto.room <= 100:
                    shutter.room, _ = Room.get_or_create(number=shutter_dto.room)
                shutter.save()
            shutters_to_save.append((shutter_dto, fields))
        self._master_controller.save_shutters(shutters_to_save)
        self.update_config(self.load_shutters())

    def load_shutter_group(self, group_id):  # type: (int) -> ShutterGroupDTO
        shutter_group = ShutterGroup.get(number=group_id)  # type: ShutterGroup
        shutter_group_dto = self._master_controller.load_shutter_group(shutter_group_id=shutter_group.number)
        shutter_group_dto.room = shutter_group.room.number if shutter_group.room is not None else None
        return shutter_group_dto

    def load_shutter_groups(self):  # type: () -> List[ShutterGroupDTO]
        shutter_group_dtos = []
        for shutter_group in ShutterGroup.select():
            shutter_group_dto = self._master_controller.load_shutter_group(shutter_group_id=shutter_group.number)
            shutter_group_dto.room = shutter_group.room.number if shutter_group.room is not None else None
            shutter_group_dtos.append(shutter_group_dto)
        return shutter_group_dtos

    def save_shutter_groups(self, shutter_groups):  # type: (List[Tuple[ShutterGroupDTO, List[str]]]) -> None
        shutter_groups_to_save = []
        for shutter_group_dto, fields in shutter_groups:
            shutter_group = ShutterGroup.get_or_none(number=shutter_group_dto.id)  # type: ShutterGroup
            if shutter_group is None:
                continue
            if 'room' in fields:
                if shutter_group_dto.room is None:
                    shutter_group.room = None
                elif 0 <= shutter_group_dto.room <= 100:
                    shutter_group.room, _ = Room.get_or_create(number=shutter_group_dto.room)
                shutter_group.save()
            shutter_groups_to_save.append((shutter_group_dto, fields))
        self._master_controller.save_shutter_groups(shutter_groups_to_save)

    # Control shutters

    def shutter_group_down(self, group_id):
        self._master_controller.shutter_group_down(group_id)

    def shutter_group_up(self, group_id):
        self._master_controller.shutter_group_up(group_id)

    def shutter_group_stop(self, group_id):
        self._master_controller.shutter_group_stop(group_id)

    def shutter_up(self, shutter_id, desired_position=None):
        return self._shutter_goto_direction(shutter_id, ShutterEnums.Direction.UP, desired_position)

    def shutter_down(self, shutter_id, desired_position=None):
        return self._shutter_goto_direction(shutter_id, ShutterEnums.Direction.DOWN, desired_position)

    def shutter_goto(self, shutter_id, desired_position):
        # Fetch and validate data
        shutter = self._get_shutter(shutter_id)
        steps = ShutterController._get_steps(shutter)
        ShutterController._validate_position(shutter_id, desired_position, steps)

        actual_position = self._actual_positions[shutter_id]
        if actual_position is None:
            raise RuntimeError('Shutter {0} has unknown actual position'.format(shutter_id))

        direction = self._get_direction(actual_position, desired_position)
        if direction == ShutterEnums.Direction.STOP:
            return self.shutter_stop(shutter_id)

        self._log('Shutter {0} setting desired position to {1}'.format(shutter_id, desired_position))

        self._desired_positions[shutter_id] = desired_position
        self._directions[shutter_id] = direction
        self._execute_shutter(shutter_id, direction)

    def shutter_stop(self, shutter_id):
        # Validate data
        self._get_shutter(shutter_id)

        self._log('Shutter {0} stopped. Removing desired position'.format(shutter_id))

        self._desired_positions[shutter_id] = None
        self._directions[shutter_id] = ShutterEnums.Direction.STOP
        self._execute_shutter(shutter_id, ShutterEnums.Direction.STOP)

    # Control operations

    def _shutter_goto_direction(self, shutter_id, direction, desired_position=None):
        # Fetch and validate data
        shutter = self._get_shutter(shutter_id)
        steps = ShutterController._get_steps(shutter)

        if desired_position is not None:
            ShutterController._validate_position(shutter_id, desired_position, steps)
        else:
            desired_position = ShutterController._get_limit(direction, steps)

        self._log('Shutter {0} setting direction to {1} {2}'.format(
            shutter_id, direction,
            'without position' if desired_position is None else 'with position {0}'.format(desired_position)
        ))

        self._desired_positions[shutter_id] = desired_position
        self._directions[shutter_id] = direction
        self._execute_shutter(shutter_id, direction)

    def _execute_shutter(self, shutter_id, direction):
        if direction == ShutterEnums.Direction.UP:
            self._master_controller.shutter_up(shutter_id)
        elif direction == ShutterEnums.Direction.DOWN:
            self._master_controller.shutter_down(shutter_id)
        elif direction == ShutterEnums.Direction.STOP:
            self._master_controller.shutter_stop(shutter_id)

    # Internal checks and validators

    def _get_shutter(self, shutter_id, return_none=False):
        shutter = self._shutters.get(shutter_id)
        if shutter is None:
            self.update_config(self.load_shutters())
            shutter = self._shutters.get(shutter_id)
            if shutter is None and return_none is False:
                raise RuntimeError('Shutter {0} is not available'.format(shutter_id))
        return shutter

    @staticmethod
    def _is_position_reached(direction, desired_position, actual_position, stopped=True):
        if desired_position == actual_position:
            return True  # Obviously reached
        if direction == ShutterEnums.Direction.STOP:
            return stopped  # Can't be decided, so return user value
        # An overshoot is considered as "position reached"
        if direction == ShutterEnums.Direction.UP:
            return actual_position < desired_position
        return actual_position > desired_position

    @staticmethod
    def _get_limit(direction, steps):
        if steps is None:
            return None
        if direction == ShutterEnums.Direction.UP:
            return 0
        return steps - 1

    @staticmethod
    def _get_direction(actual_position, desired_position):
        if actual_position == desired_position:
            return ShutterEnums.Direction.STOP
        if actual_position < desired_position:
            return ShutterEnums.Direction.UP
        return ShutterEnums.Direction.DOWN

    @staticmethod
    def _get_steps(shutter):  # type: (ShutterDTO) -> Optional[int]
        steps = shutter.steps
        if steps in [0, 1, None]:
            # These step values are considered "not configured" and thus "no position support"
            return None
        return steps

    @staticmethod
    def _validate_position(shutter_id, position, steps):
        if steps is None:
            raise RuntimeError('Shutter {0} does not support positioning'.format(shutter_id))
        if not (0 <= position < steps):
            raise RuntimeError('Shutter {0} has a position limit of 0 <= position <= {1}'.format(shutter_id, steps - 1))

    # Reporting

    def _report_shutter_state(self, shutter_id, new_state):
        shutter = self._get_shutter(shutter_id, return_none=True)
        if shutter is None:
            logger.warning('Shutter {0} unknown'.format(shutter_id))
            return
        steps = ShutterController._get_steps(shutter)

        self._directions[shutter_id] = ShutterController.STATE_DIRECTION_MAP[new_state]
        self._log('Shutter {0} reports state {1}, which is direction {2}'.format(shutter_id, new_state, self._directions[shutter_id]))

        current_state_timestamp, current_state = self._states[shutter_id]
        if new_state == current_state or (new_state == ShutterEnums.State.STOPPED and current_state in [ShutterEnums.State.DOWN, ShutterEnums.State.UP]):
            self._log('Shutter {0} new state {1} ignored since it equals {2}'.format(shutter_id, new_state, current_state))
            return  # State didn't change, nothing to do

        if new_state != ShutterEnums.State.STOPPED:
            # Shutter started moving
            self._states[shutter_id] = [time.time(), new_state]
            self._log('Shutter {0} started moving'.format(shutter_id))
        else:
            direction = ShutterController.STATE_DIRECTION_MAP[current_state]
            if steps is None:
                # Time based state calculation
                timer = getattr(shutter, 'timer_{0}'.format(direction.lower()))
                if timer is None:
                    self._log('Shutter {0} is time-based but has no valid timer. New state {1}'.format(shutter_id, ShutterEnums.State.STOPPED))
                    new_state = ShutterEnums.State.STOPPED
                else:
                    threshold = 0.90 * timer  # Allow 10% difference
                    elapsed_time = time.time() - current_state_timestamp
                    if elapsed_time >= threshold:  # The shutter was going up/down for the whole `timer`. So it's now up/down
                        self._log('Shutter {0} going {1} passed time threshold. New state {2}'.format(shutter_id, direction, ShutterController.DIRECTION_END_STATE_MAP[direction]))
                        new_state = ShutterController.DIRECTION_END_STATE_MAP[direction]
                    else:
                        self._log('Shutter {0} going {1} did not pass time threshold ({2:.2f}s vs {3:.2f}s). New state {4}'.format(shutter_id, direction, elapsed_time, threshold, ShutterEnums.State.STOPPED))
                        new_state = ShutterEnums.State.STOPPED
            else:
                # Supports position, so state will be calculated on position
                limit_position = ShutterController._get_limit(direction, steps)
                if ShutterController._is_position_reached(direction, limit_position, self._actual_positions[shutter_id]):
                    self._log('Shutter {0} going {1} reached limit. New state {2}'.format(shutter_id, direction, ShutterController.DIRECTION_END_STATE_MAP[direction]))
                    new_state = ShutterController.DIRECTION_END_STATE_MAP[direction]
                else:
                    self._log('Shutter {0} going {1} did not reach limit. New state {2}'.format(shutter_id, direction, ShutterEnums.State.STOPPED))
                    new_state = ShutterEnums.State.STOPPED

            self._states[shutter_id] = [time.time(), new_state]

        self._send_event(shutter_id, shutter, self._states[shutter_id])

    def get_states(self):
        all_states = []
        for i in sorted(self._states.keys()):
            all_states.append(self._states[i][1])
        return {'status': all_states,
                'detail': {shutter_id: {'state': self._states[shutter_id][1],
                                        'actual_position': self._actual_positions[shutter_id],
                                        'desired_position': self._desired_positions[shutter_id]}
                           for shutter_id in self._shutters}}

    def _send_event(self, shutter_id, shutter_data, shutter_state):
        for callback in self._event_subscriptions:
            callback(GatewayEvent(event_type=GatewayEvent.Types.SHUTTER_CHANGE,
                                  data={'id': shutter_id,
                                        'status': {'state': shutter_state[1].upper()},
                                        'location': {'room_id': Toolbox.nonify(shutter_data.room, 255)}}))
