#!/usr/bin/env python
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

import os
import unittest

try:
    from unittest import mock
except ImportError:
    import mock

from host_controller.command_processor import command_reproduce


class CommandReproduceTest(unittest.TestCase):
    """Tests for reproduce command processor"""

    @mock.patch("host_controller.command_processor.command_reproduce.logging")
    def testGenerateSetupCommandsNoFetchInfo(self, mock_logging):
        mock_msg = mock.Mock()
        mock_msg.vendor_branch = ""
        command = command_reproduce.CommandReproduce()
        ret = command.GenerateSetupCommands(mock_msg, ["serial1", "serial2"])
        self.assertEqual(ret, [])
        mock_logging.error.assert_called_with(
            "Report contains no fetch information. "
            "Aborting pre-test setups on the device(s).")

    @mock.patch("host_controller.command_processor.command_reproduce.logging")
    def testGenerateSetupCommandsNoSerial(self, mock_logging):
        mock_msg = mock.Mock()
        mock_msg.vendor_branch = "some_branch"
        command = command_reproduce.CommandReproduce()
        ret = command.GenerateSetupCommands(mock_msg, [])
        self.assertEqual(ret, [])
        mock_logging.error.assert_called_with(
            "Device serial number(s) not given. "
            "Aborting pre-test setups on the device(s).")

    def testGenerateTestSuiteFetchCommandGCS(self):
        report_msg = mock.Mock()
        report_msg.branch = "gs://bucket/path/to/vts/release"
        report_msg.target = "android-vts.zip"
        report_msg.suite_name = "VTS"
        command = command_reproduce.CommandReproduce()
        ret = command.GenerateTestSuiteFetchCommand(report_msg)
        self.assertEqual(
            ret, "fetch --type=gcs "
            "--path=gs://bucket/path/to/vts/release/android-vts.zip "
            "--set_suite_as=vts")

    @mock.patch(
        "host_controller.command_processor.command_reproduce.SchedCfgMsg")
    @mock.patch("host_controller.command_processor.command_reproduce.logging")
    def testGenerateTestSuiteFetchCommandIndexError(self, mock_logging,
                                                    mock_sched_cfg_msg):
        report_msg = mock.Mock()
        report_msg.branch = "git_whatever-release"
        report_msg.target = "test_suites_bitness"
        report_msg.build_id = "1234567"
        report_msg.suite_name = "VTS"
        report_msg.schedule_config.build_target = []
        mock_test_schedule_msg = mock.Mock()
        mock_test_schedule_msg.test_pab_account_id = "1234567898765"
        mock_sched_cfg_msg.TestScheduleConfigMessage.return_value = (
            mock_test_schedule_msg)
        command = command_reproduce.CommandReproduce()
        ret = command.GenerateTestSuiteFetchCommand(report_msg)
        mock_logging.exception.assert_called()
        self.assertEqual(ret, "fetch --type=pab --branch=git_whatever-release "
                         "--target=test_suites_bitness --build_id=1234567 "
                         "--artifact_name=android-vts.zip "
                         "--account_id=1234567898765")

    @mock.patch(
        "host_controller.command_processor.command_reproduce.SchedCfgMsg")
    def testGenerateTestSuiteFetchCommandPAB(self, mock_sched_cfg_msg):
        report_msg = mock.Mock()
        report_msg.branch = "git_whatever-release"
        report_msg.target = "test_suites_bitness"
        report_msg.build_id = "1234567"
        report_msg.suite_name = "VTS"
        mock_build_target_msg = mock.Mock()
        mock_test_schedule_msg = mock.Mock()
        mock_test_schedule_msg.test_pab_account_id = "987654321"
        mock_build_target_msg.test_schedule = []
        mock_build_target_msg.test_schedule.append(mock_test_schedule_msg)
        report_msg.schedule_config.build_target = []
        report_msg.schedule_config.build_target.append(mock_build_target_msg)
        mock_sched_cfg_msg.TestScheduleConfigMessage.return_value = (
            mock_test_schedule_msg)

        command = command_reproduce.CommandReproduce()
        ret = command.GenerateTestSuiteFetchCommand(report_msg)
        self.assertEqual(ret, "fetch --type=pab --branch=git_whatever-release "
                         "--target=test_suites_bitness --build_id=1234567 "
                         "--artifact_name=android-vts.zip "
                         "--account_id=987654321")

    @mock.patch("host_controller.console.Console")
    @mock.patch("host_controller.command_processor.command_reproduce.logging")
    def testGetResultFromGCSNoTestSuite(self, mock_logging, mock_console):
        report_msg = mock.Mock()
        report_msg.result_path = "gs://bucket/path/to/log/files"
        mock_console.test_suite_info = {}
        command = command_reproduce.CommandReproduce()
        command._SetUp(mock_console)
        ret = command.GetResultFromGCS("/mock_bin/gsutil", report_msg, "vts")
        self.assertFalse(ret)
        mock_logging.exception.assert_called()

    @mock.patch("host_controller.console.Console")
    @mock.patch("host_controller.command_processor.command_reproduce.os")
    def testGetResultFromGCSMkdirResults(self, mock_os, mock_console):
        report_msg = mock.Mock()
        report_msg.result_path = "gs://bucket/path/to/log/files"
        mock_console.test_suite_info = {
            "vts": "tmp/android-vts/tools/vts-tradefed"
        }
        mock_os.path.exists.return_value = False
        mock_os.path.join = os.path.join
        mock_os.path.dirname = os.path.dirname
        command = command_reproduce.CommandReproduce()
        command._SetUp(mock_console)
        command.GetResultFromGCS("/mock_bin/gsutil", report_msg, "vts")
        mock_os.mkdir.assert_called_with("tmp/android-vts/tools/../results")

    @mock.patch("host_controller.console.Console")
    @mock.patch(
        "host_controller.command_processor.command_reproduce.gcs_utils")
    @mock.patch("host_controller.command_processor.command_reproduce.os")
    @mock.patch("host_controller.command_processor.command_reproduce.logging")
    def testGetResultFromGCSNoResult(self, mock_logging, mock_os,
                                     mock_gcs_util, mock_console):
        report_msg = mock.Mock()
        report_msg.result_path = "gs://bucket/path/to/log/files"
        mock_console.test_suite_info = {
            "vts": "tmp/android-vts/tools/vts-tradefed"
        }
        mock_gcs_util.List.return_value = [
            "some_log1.zip", "some_log2.zip", "not_a_result.zip"
        ]
        command = command_reproduce.CommandReproduce()
        command._SetUp(mock_console)
        ret = command.GetResultFromGCS("/mock_bin/gsutil", report_msg, "vts")
        self.assertFalse(ret)

    @mock.patch("host_controller.console.Console")
    @mock.patch(
        "host_controller.command_processor.command_reproduce.gcs_utils")
    @mock.patch("host_controller.command_processor.command_reproduce.os")
    @mock.patch("host_controller.command_processor.command_reproduce.zipfile")
    def testGetResultFromGCS(self, mock_zipfile, mock_os, mock_gcs_util,
                             mock_console):
        report_msg = mock.Mock()
        report_msg.result_path = "gs://bucket/path/to/log/files"
        mock_console.test_suite_info = {
            "vts": "tmp/android-vts/tools/vts-tradefed"
        }
        mock_zip_ref = mock.Mock()
        mock_zip_ref.__enter__ = mock.Mock(return_value=mock_zip_ref)
        mock_zip_ref.__exit__ = mock.Mock(return_value=None)
        mock_zipfile.ZipFile.return_value = mock_zip_ref
        mock_gcs_util.List.return_value = [
            "some_log1.zip", "some_log2.zip", "results_some_hash.zip"
        ]
        mock_gcs_util.Copy.return_value = True
        mock_os.path.join = os.path.join
        mock_os.path.exists.return_value = False
        mock_os.path.dirname = os.path.dirname
        command = command_reproduce.CommandReproduce()
        command._SetUp(mock_console)
        ret = command.GetResultFromGCS("/mock_bin/gsutil", report_msg, "vts")
        self.assertTrue(ret)
        mock_zip_ref.extractall.assert_called_with(
            "tmp/android-vts/tools/../results")

    @mock.patch("host_controller.console.Console")
    @mock.patch(
        "host_controller.command_processor.command_reproduce.gcs_utils")
    @mock.patch("host_controller.command_processor.command_reproduce.logging")
    def testCommandReproduceGsutilAbsent(self, mock_logging, mock_gcs_util,
                                         mock_console):
        mock_gcs_util.GetGsutilPath.return_value = ""
        command = command_reproduce.CommandReproduce()
        command._SetUp(mock_console)
        ret = command._Run("--report_path=gs://bucket/path/to/report/file")
        self.assertFalse(ret)
        mock_logging.error.assert_called_with(
            "Please check gsutil is installed and on your PATH")

    @mock.patch("host_controller.console.Console")
    @mock.patch(
        "host_controller.command_processor.command_reproduce.gcs_utils")
    @mock.patch("host_controller.command_processor.command_reproduce.logging")
    def testCommandReproduceInvalidURL(self, mock_logging, mock_gcs_util,
                                       mock_console):
        mock_gcs_util.GetGsutilPath.return_value = "/mock_bin/gsutil"
        command = command_reproduce.CommandReproduce()
        command._SetUp(mock_console)
        ret = command._Run("--report_path=/some/path/to/report/file")
        self.assertFalse(ret)
        mock_logging.error.assert_called_with("%s is not a correct GCS path.",
                                              "/some/path/to/report/file")


if __name__ == "__main__":
    unittest.main()
