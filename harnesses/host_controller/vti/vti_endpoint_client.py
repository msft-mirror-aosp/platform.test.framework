#
# Copyright (C) 2017 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import requests
import json


class VtiEndpointClient(object):
    """VTI endpoint client.

    Attributes:
        _url: string, the base URL of an endpoint API.
    """

    def __init__(self, url):
        if not url.startswith(("https://")) and not url.startswith("http://"):
            url = "https://" + url
        if url.endswith("appspot.com"):
            url += "/_ah/api/"
        self._url = url

    def UploadBuildInfo(self, builds):
        """Uploads the given build information to VTI.

        Args:
            builds: a list of dicts, containing info about all new
                    builds found.

        Returns:
            True if successful, False otherwise.
        """
        url = self._url + "build_info/v1/set"
        headers = {"content-type": "application/json",
                   "Accept-Charset": "UTF-8"}
        fail = False
        for build in builds:
            response = requests.post(url, data=json.dumps(build),
                                     headers=headers)
            if str(response) != "<Response [200]>":
                print "UploadDeviceInfo error: %s" % response
                fail = True
        if fail:
            return False
        return True

    def UploadDeviceInfo(self, hostname, devices):
        """Uploads the given device information to VTI.

        Args:
            hostname: string, the hostname of a target host.
            devices: a list of dicts, containing info about all detected
                     devices that are attached to the host.

        Returns:
            True if successful, False otherwise.
        """
        url = self._url + "host_info/v1/set"
        payload = {}
        payload["hostname"] = hostname
        payload["devices"] = []
        for device in devices:
            new_device = {
                "serial": device["serial"],
                "product": device["product"],
                "status": device["status"]}
            payload["devices"].append(new_device)
        headers = {"content-type": "application/json",
                   "Accept-Charset": "UTF-8"}
        response = requests.post(url, data=json.dumps(payload), headers=headers)
        if str(response) != "<Response [200]>":
            print "UploadDeviceInfo error: %s" % response
            return False
        return True
