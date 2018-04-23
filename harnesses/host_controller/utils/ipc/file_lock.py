#
# Copyright (C) 2018 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import fcntl
import logging
import os

from host_controller import common


class FileLock(object):
    """Class for using files as a locking mechanism for devices.

    This is for checking whether a certain device is running a job or not when
    the automated self-update happens.

    Attributes:
        _devlock_dir: string, represent the home directory of the user.
        _lock_fd: dict, maps serial number of the devices and file descriptor.
    """

    def __init__(self):
        self._lock_fd = {}
        self._devlock_dir = os.path.join(
            os.path.expanduser("~"), common._DEVLOCK_DIR)
        if not os.path.exists(self._devlock_dir):
            os.mkdir(self._devlock_dir)
        file_list = [file_name for file_name in os.listdir(self._devlock_dir)]
        for file_name in file_list:
            if os.path.isfile(os.path.join(self._devlock_dir, file_name)):
                self._OpenFile(file_name)

    def _OpenFile(self, serial):
        """Opens the given lock file and store the file descriptor to _lock_fd.

        Args:
            serial: string, serial number of a device.
        """
        if serial in self._lock_fd and self._lock_fd[serial]:
            logging.info("Lock for the device %s already exists." % serial)
            return

        try:
            self._lock_fd[serial] = open(
                os.path.join(self._devlock_dir, serial), "w+")
        except IOError as e:
            logging.exception(e)
            return False

    def LockDevice(self, serial):
        """Tries to lock the file corresponding to "serial".

        Args:
            serial: string, serial number of a device.

        Returns:
            True if successfully acquired the lock. False otherwise.
        """
        if serial not in self._lock_fd:
            ret = self._OpenFile(serial)
            if ret == False:
                return ret

        try:
            fcntl.lockf(self._lock_fd[serial], fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError as e:
            logging.exception(e)
            return False

        return True

    def UnlockDevice(self, serial):
        """Releases the lock file corresponding to "serial".

        Args:
            serial: string, serial number of a device.
        """
        if serial not in self._lock_fd:
            logging.error("Lock for the device %s does not exist." % serial)
            return False

        fcntl.lockf(self._lock_fd[serial], fcntl.LOCK_UN)
