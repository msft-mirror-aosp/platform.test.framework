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

import collections
import os
import shutil


class BuildInfo(dict):
    """dict class for fetched device imgs, test suites, etc."""

    def __init__(self):
        super(BuildInfo, self).__init__()

    def __setitem__(self, key, value):
        """__setitem__ for BuildInfo dict.

        Remove pre-fetched file which has the same use in HC
        if the old one has different file name from the new one.

        Args:
            key: string, key for the path to the fetched file.
            value: string, path to the newly fetched file.
        """
        if key in self and value != self[key]:
            print("Removing pre-fetched item: %s" % self[key])
            try:
                if os.path.isfile(self[key]):
                    os.remove(self[key])
                elif os.path.isdir(self[key]):
                    shutil.rmtree(self[key])
                else:
                    print("%s is not found" % self[key])
            except OSError as e:
                print("ERROR: error on file remove %s" % e)

        super(BuildInfo, self).__setitem__(key, value)

    def update(self, other=None, **kwargs):
        """Overrides update() in order to call BuildInfo.__setitem__().

        Args:
            other: dict or iterable of key/value pairs. Update self
                   using this argument
            **kwargs: The optional attributes.
        """
        if other is not None:
            for k, v in other.items() if isinstance(
                    other, collections.Mapping) else other:
                self[k] = v
        for k, v in kwargs.items():
            self[k] = v
