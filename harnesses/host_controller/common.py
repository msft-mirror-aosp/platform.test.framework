#
# Copyright (C) 2018 The Android Open Source Project
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

# The default Partner Android Build (PAB) public account.
# To obtain access permission, please reach out to Android partner engineering
# department of Google LLC.

from vti.test_serving.proto import TestScheduleConfigMessage_pb2 as pb

_DEFAULT_ACCOUNT_ID = '543365459'

# The default Partner Android Build (PAB) internal account.
_DEFAULT_ACCOUNT_ID_INTERNAL = '541462473'

# The key value used for getting a fetched .zip android img file.
FULL_ZIPFILE = "full-zipfile"
# The key of an item that stores the unziped files of a full image zip file.
FULL_ZIPFILE_DIR = "full-zipfile-dir"

# The key of an item that stores the fetch GSI image (.zip) file.
GSI_ZIPFILE = "gsi-zipfile"
# The key of an item that stores the unziped files of a GSI image zip file.
GSI_ZIPFILE_DIR = "gsi-zipfile-dir"

# The default value for "flash --current".
_DEFAULT_FLASH_IMAGES = [
    FULL_ZIPFILE,
    FULL_ZIPFILE_DIR,
    "bootloader.img",
    "boot.img",
    "cache.img",
    "radio.img",
    "system.img",
    "userdata.img",
    "vbmeta.img",
    "vendor.img",
]

# The environment variable for default serial numbers.
_ANDROID_SERIAL = "ANDROID_SERIAL"

_DEVICE_STATUS_DICT = {
    "unknown": 0,
    "fastboot": 1,
    "online": 2,
    "ready": 3,
    "use": 4,
    "error": 5}

_STORAGE_TYPE_DICT = {
    pb.UNKNOWN_BUILD_STORAGE_TYPE: "unknown",
    pb.BUILD_STORAGE_TYPE_PAB: "pab",
    pb.BUILD_STORAGE_TYPE_GCS: "gcs",
}

_STORAGE_TYPE_DICT_REVERSE = {
    "unknown": pb.UNKNOWN_BUILD_STORAGE_TYPE,
    "pab": pb.BUILD_STORAGE_TYPE_PAB,
    "gcs": pb.BUILD_STORAGE_TYPE_GCS,
}

# Default SPL date, used for gsispl command
_SPL_DEFAULT_DAY = 5

# Maximum number of leased jobs per host.
_MAX_LEASED_JOBS = 14

# Defualt access point for dut wifi_on command.
_DEFAULT_WIFI_AP = "GoogleGuest"

# SoC name list.
SDM845 = "sdm845"

UNIVERSAL9810 = "universal9810"

# Relative path to the "results" directory from the tools directory.
_RESULTS_BASE_PATH = "../results"

# Test result file contains invoked test plan results.
_TEST_RESULT_XML = "test_result.xml"

# XML tag name whose attribute is test plan.
_RESULT_TAG = "Result"

# XML tag name whose attributes are about the build info of the device.
_BUILD_TAG = "Build"

# XML tag name whose attributes are pass/fail count, modules run/total count.
_SUMMARY_TAG = "Summary"

# The key value for retrieving test plan and etc. from the result xml
_SUITE_PLAN_ATTR_KEY = "suite_plan"

_SUITE_BUILD_NUM_ATTR_KEY = "suite_build_number"

_SUITE_VERSION_ATTR_KEY = "suite_version"

_HOST_NAME_ATTR_KEY = "host_name"

_START_TIME_ATTR_KEY = "start"

_END_TIME_ATTR_KEY = "end"

_SUITE_NAME_ATTR_KEY = "suite_name"

# The key value for retrieving build fingerprint values from the result xml.
_SYSTEM_FINGERPRINT_ATTR_KEY = "build_system_fingerprint"

_VENDOR_FINGERPRINT_ATTR_KEY = "build_vendor_fingerprint"

# The key value for retrieving passed testcase count
_PASSED_ATTR_KEY = "pass"

# The key value for retrieving failed testcase count
_FAILED_ATTR_KEY = "failed"

# The key value for retrieving total module count
_MODULES_TOTAL_ATTR_KEY = "modules_total"

# The key value for retrieving run module count
_MODULES_DONE_ATTR_KEY = "modules_done"

# VTSLAB package version file
_VTSLAB_VERSION_TXT = "version.txt"

_VTSLAB_VERSION_DEFAULT_VALUE = "000000_000000:00000000"

