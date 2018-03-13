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

import os
import xml.etree.ElementTree as ET
import zipfile

from host_controller.build import build_provider_gcs
from host_controller.command_processor import base_command_processor

from vts.utils.python.common import cmd_utils

# Test result file contains invoked test plan results.
_TEST_RESULT_XML = "test_result.xml"

# XML tag name whose attributes are pass/fail count, modules run/total count.
_SUMMARY_TAG = "Summary"

# The key value for retrieving failed testcase count
_FAILED_ATTR_KEY = "failed"

# The key value for retrieving total module count
_MODULES_TOTAL_ATTR_KEY = "modules_total"

# The key value for retrieving run module count
_MODULES_DONE_ATTR_KEY = "modules_done"

# The key value for retrieving test plan from the result xml
_SUITE_PLAN_ATTR_KEY = "suite_plan"


class CommandRetry(base_command_processor.BaseCommandProcessor):
    """Command processor for retry command.

    Attributes:
        _result_suite_plan: string, test plan info from latest/downloaded
                            test result.
        _result_skip_count: int, number of skipped module from the result.
        _result_fail_count: int, number of failed test cases from the result.
    """

    command = "retry"
    command_detail = "Retry last run test plan for certain times."

    def __init__(self):
        self._result_suite_plan = ""
        self._result_skip_count = 0
        self._result_fail_count = 0

    def ParseXml(self, path_to_xml_file):
        """Parses test_result.xml file and get information about the test.

        Args:
            path_to_xml_file: string, path to the test_result.xml file
        """
        tree = ET.parse(path_to_xml_file)
        root = tree.getroot()
        self._result_suite_plan = root.attrib[_SUITE_PLAN_ATTR_KEY]

        summary = root.find(_SUMMARY_TAG).attrib
        self._result_fail_count = int(summary[_FAILED_ATTR_KEY])
        self._result_skip_count = int(summary[_MODULES_TOTAL_ATTR_KEY]) - int(
            summary[_MODULES_DONE_ATTR_KEY])

    def IsResultZipFile(self, zip_ref):
        """Determines whether the given zip_ref is the right result archive.

        Need to check the number of contents of the zip file since
        the "log-result_<>.zip" file only contains "test_result.xml",
        but cannot parsed by vts-tf properly when trying to do the retry.

        Args:
            zip_ref: ZipFile, reference to the downloaded results_<>.zip file

        Returns:
            True if the downloaded zip file is usable from vts-fs,
            False otherwise.
        """
        if len(zip_ref.namelist()) > 1:
            for name in zip_ref.namelist():
                if _TEST_RESULT_XML in name:
                    return True
        return False

    def GetResultFromGCS(self, gcs_result_path, local_results_dir):
        """Downloads a vts-tf result zip archive from GCS.

        And unzip the file to "android-vts/results/" path so
        the vts-tf will parse the result correctly.

        Args:
            gcs_result_path: string, path to GCS file.
            local_results_dir: string, abs path to the result directory of
                               currently running vts-tf.
        Returns:
            A string which is the name of unzipped result directory.
            None if the download has failed or the downloaded zip file
            is not a correct result archive.
        """
        gsutil_path = build_provider_gcs.BuildProviderGCS.GetGsutilPath()
        if not gsutil_path:
            print("Please check gsutil is installed and on your PATH")
            return None

        if (not gcs_result_path.startswith("gs://")
                or not build_provider_gcs.BuildProviderGCS.IsGcsFile(
                    gsutil_path, gcs_result_path)):
            print("%s is not correct GCS url." % gcs_result_path)
            return None
        if not gcs_result_path.endswith(".zip"):
            print("%s is not a correct result archive file." % gcs_result_path)
            return None

        if not os.path.exists(local_results_dir):
            os.mkdir(local_results_dir)
        copy_command = "%s cp %s %s" % (gsutil_path, gcs_result_path,
                                        local_results_dir)
        stdout, stderr, err_code = cmd_utils.ExecuteOneShellCommand(
            copy_command)
        if err_code != 0:
            print("Error in copy file from %s (code %s)." % err_code)
            return None
        result_zip = os.path.join(local_results_dir,
                                  gcs_result_path.split("/")[-1])
        with zipfile.ZipFile(result_zip, mode="r") as zip_ref:
            if self.IsResultZipFile(zip_ref):
                unzipped_result_dir = zip_ref.namelist()[0].rstrip("/")
                zip_ref.extractall(local_results_dir)
                return unzipped_result_dir
            else:
                print("Not a correct vts-tf result archive file.")
                return None

    # @Override
    def SetUp(self):
        """Initializes the parser for retry command."""
        self.arg_parser.add_argument(
            "--count",
            type=int,
            default=30,
            help="Retry count. Default retry count is 30.")
        self.arg_parser.add_argument(
            "--force-count",
            type=int,
            default=3,
            help="Forced retry count. Retry certain test plan for the given "
            "times whether all testcases has passed or not.")
        self.arg_parser.add_argument(
            "--result-from-gcs",
            help="Google Cloud Storage URL from which the result is downloaded. "
            "Will retry based on the fetched result data")

    # @Override
    def Run(self, arg_line):
        """Retry last run plan for certain times."""
        args = self.arg_parser.ParseLine(arg_line)
        retry_count = args.count
        force_retry_count = args.force_count

        if "vts" not in self.console.test_suite_info:
            print("test_suite_info doesn't have 'vts': %s" %
                  self.console.test_suite_info)
            return False

        tools_path = os.path.dirname(self.console.test_suite_info["vts"])
        vts_root_path = os.path.dirname(tools_path)
        results_path = os.path.join(vts_root_path, "results")

        unzipped_result_dir = ""
        unzipped_result_session_id = -1
        if args.result_from_gcs:
            unzipped_result_dir = self.GetResultFromGCS(
                args.result_from_gcs, results_path)
            if not unzipped_result_dir:
                return False

        former_results = [
            result for result in os.listdir(results_path)
            if os.path.isdir(os.path.join(results_path, result))
            and not os.path.islink(os.path.join(results_path, result))
        ]
        former_result_count = len(former_results)
        if former_result_count < 1:
            print("No test plan has been run yet, former results count is %d" %
                  former_result_count)
            return False

        if unzipped_result_dir:
            former_results.sort()
            unzipped_result_session_id = former_results.index(
                unzipped_result_dir)

        for result_index in range(retry_count):
            if unzipped_result_session_id >= 0:
                session_id = unzipped_result_session_id
                unzipped_result_session_id = -1
                latest_result_xml_path = os.path.join(
                    results_path, unzipped_result_dir, _TEST_RESULT_XML)
            else:
                session_id = former_result_count - 1 + result_index
                latest_result_xml_path = os.path.join(results_path, "latest",
                                                      _TEST_RESULT_XML)
                if not os.path.exists(latest_result_xml_path):
                    latest_result_xml_path = os.path.join(
                        results_path, former_results[-1], _TEST_RESULT_XML)

            self.ParseXml(latest_result_xml_path)
            if (result_index >= force_retry_count
                    and self._result_skip_count == 0
                    and self._result_fail_count == 0):
                print("All modules have run and passed. "
                      "Skipping remaining %d retry runs." %
                      (retry_count - result_index))
                break

            retry_test_command = "test --keep-result -- %s --retry %d" % (
                self._result_suite_plan, session_id)
            self.console.onecmd(retry_test_command)

            for result in os.listdir(results_path):
                new_result = os.path.join(results_path, result)
                if (os.path.isdir(new_result)
                        and not os.path.islink(new_result)
                        and result not in former_results):
                    former_results.append(result)
                    break
