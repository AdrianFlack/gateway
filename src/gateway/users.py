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
The users module contains the UserController class, which provides methods for creating
and authenticating users.
"""

from __future__ import absolute_import
import sqlite3
import hashlib
import uuid
import time
from random import randint
from ioc import Injectable, Inject, Singleton, INJECTED


@Injectable.named('user_controller')
@Singleton
class UserController(object):
    """ The UserController provides methods for the creation and authentication of users. """

    TERMS_VERSION = 1

    @Inject
    def __init__(self, user_db=INJECTED, user_db_lock=INJECTED, config=INJECTED, token_timeout=INJECTED):
        """ Constructor a new UserController.

        :param user_db: filename of the sqlite database used to store the users and tokens.
        :param lock: shared lock for the given DB
        :type lock: threading.Lock
        :param config: Contains the OpenMotics cloud username and password.
        :type config: A dict with keys 'username' and 'password'.
        :param token_timeout: the number of seconds a token is valid.
        """
        self._lock = user_db_lock
        self._config = config
        self._connection = sqlite3.connect(user_db,
                                           detect_types=sqlite3.PARSE_DECLTYPES,
                                           check_same_thread=False,
                                           isolation_level=None)
        self._cursor = self._connection.cursor()
        self._token_timeout = token_timeout
        self._tokens = {}
        self._schema = {'username': "TEXT UNIQUE",
                        'password': "TEXT",
                        'role': "TEXT",
                        'enabled': "INT",
                        'accepted_terms': "INT default 0"}
        self._check_tables()

        # Create the user for the cloud
        self.create_user(self._config['username'].lower(), self._config['password'], "admin", True, True)

    def _execute(self, *args, **kwargs):
        lock = kwargs.pop('lock', True)
        try:
            if lock:
                self._lock.acquire()
            return self._cursor.execute(*args, **kwargs)
        except sqlite3.OperationalError:
            time.sleep(randint(1, 20) / 10.0)
            return self._cursor.execute(*args, **kwargs)
        finally:
            if lock:
                self._lock.release()

    def _check_tables(self):
        """
        Creates tables and execute migrations
        """
        with self._lock:
            self._execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, {0});".format(
                ", ".join(['{0} {1}'.format(key, value) for key, value in self._schema.items()])
            ), lock=False)
            fields = []
            for row in self._execute("PRAGMA table_info('users');", lock=False):
                fields.append(row[1])
            for field, field_type in self._schema.items():
                if field not in fields:
                    self._execute("ALTER TABLE users ADD COLUMN {0} {1};".format(field, field_type), lock=False)

    @staticmethod
    def _hash(password):
        # type: (str) -> str
        """ Hash the password using sha1. """
        sha = hashlib.sha1()
        sha.update("OpenMotics".encode('utf-8'))
        sha.update(password.encode('utf-8'))
        return sha.hexdigest()

    def create_user(self, username, password, role, enabled, accept_terms=False):
        """ Create a new user using a username, password, role and enabled. The username is case
        insensitive.

        :param username: username for the newly created user.
        :param password: password for the newly created user.
        :param role: role for the newly created user.
        :param enabled: boolean, only enabled users can log into the system.
        :param accept_terms: indicates whether the user has accepted the terms
        """
        username = username.lower()
        accepted_terms = UserController.TERMS_VERSION if accept_terms else 0

        self._execute("INSERT OR REPLACE INTO users (username, password, role, enabled, accepted_terms) VALUES (?, ?, ?, ?, ?);",
                      (username, UserController._hash(password), role, int(enabled), accepted_terms))

    def get_usernames(self):
        """ Get all usernames.

        :returns: a list of strings.
        """
        usernames = []
        for row in self._execute("SELECT username FROM users;"):
            usernames.append(row[0])
        return usernames

    def remove_user(self, username):
        """ Remove a user.

        :param username: the name of the user to remove.
        """
        username = username.lower()

        if self.get_role(username) == "admin" and self._get_num_admins() == 1:
            raise Exception("Cannot delete last admin account")
        else:
            self._execute("DELETE FROM users WHERE username = ?;", (username,))

            to_remove = []
            for token in self._tokens:
                if self._tokens[token][0] == username:
                    to_remove.append(token)

            for token in to_remove:
                del self._tokens[token]

    def _get_num_admins(self):
        """ Get the number of admin users in the system. """
        for row in self._execute("SELECT count(*) FROM users WHERE role = ?", ("admin",)):
            return row[0]
        return 0

    def login(self, username, password, accept_terms=None, timeout=None):
        """ Login with a username and password, returns a token for this user.

        :returns: a token that identifies this user, None for invalid credentials.
        """
        username = username.lower()
        if timeout is not None:
            try:
                timeout = int(timeout)
                timeout = min(60 * 60 * 24 * 30, max(60 * 60, timeout))
            except ValueError:
                timeout = None
        if timeout is None:
            timeout = self._token_timeout

        for row in self._execute("SELECT id, accepted_terms FROM users WHERE username = ? AND password = ? AND enabled = ?;",
                                 (username, UserController._hash(password), 1)):
            user_id, accepted_terms = row[0], row[1]
            if accepted_terms == UserController.TERMS_VERSION:
                return True, self._gen_token(username, time.time() + timeout)
            if accept_terms is True:
                self._execute("UPDATE users SET accepted_terms = ? WHERE id = ?;",
                              (UserController.TERMS_VERSION, user_id))
                return True, self._gen_token(username, time.time() + timeout)
            return False, 'terms_not_accepted'
        return False, 'invalid_credentials'

    def logout(self, token):
        """ Removes the token from the controller. """
        self._tokens.pop(token, None)

    def get_role(self, username):
        """ Get the role for a certain user. Returns None is user was not found. """
        username = username.lower()

        for row in self._execute("SELECT role FROM users WHERE username = ?;", (username,)):
            return row[0]

        return None

    def _gen_token(self, username, valid_until):
        """ Generate a token and insert it into the tokens dict. """
        ret = uuid.uuid4().hex
        self._tokens[ret] = (username, valid_until)

        # Delete the expired tokens
        for token in list(self._tokens):
            if self._tokens[token][1] < time.time():
                self._tokens.pop(token, None)

        return ret

    def check_token(self, token):
        """ Returns True if the token is valid, False if the token is invalid. """
        if token is None or token not in self._tokens:
            return False
        else:
            return self._tokens[token][1] >= time.time()

    def close(self):
        """ Cose the database connection. """
        self._connection.close()
