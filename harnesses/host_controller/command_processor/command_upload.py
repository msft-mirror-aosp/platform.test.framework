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

import logging
import os
import shutil

from host_controller import common
from host_controller.build import build_provider_gcs
from host_controller.command_processor import base_command_processor
from host_controller.utils.parser import xml_utils

from vts.utils.python.common import cmd_utils

from vti.dashboard.proto import TestSuiteResultMessage_pb2 as SuiteResMsg


class CommandUpload(base_command_processor.BaseCommandProcessor):
    """Command processor for upload command.

    Attributes:
        arg_parser: ConsoleArgumentParser object, argument parser.
        console: cmd.Cmd console object.
        command: string, command name which this processor will handle.
        command_detail: string, detailed explanation for the command.
    """

    command = "upload"
    command_detail = "Upload <src> file to <dest> Google Cloud Storage. In <src> and <dest>, variables enclosed in {} are replaced with the values stored in the console."

    # @Override
    def SetUp(self):
        """Initializes the parser for upload command."""
        self.arg_parser.add_argument(
            "--src",
            required=True,
            default="latest-system.img",
            help="Path to a source file to upload. Only single file can be "
            "uploaded per once. Use 'latest- prefix to upload the latest "
            "fetch images. e.g. --src=latest-system.img  If argument "
            "value is not given, the recently fetched system.img will be "
            "uploaded.")
        self.arg_parser.add_argument(
            "--dest",
            required=True,
            help="Google Cloud Storage URL to which the file is uploaded.")
        self.arg_parser.add_argument(
            "--report_path",
            help="Google Cloud Storage URL, the dest path of a report file")
        self.arg_parser.add_argument(
            "--clear_results",
            default=False,
            help="True to clear all the results after the upload.")
        self.arg_parser.add_argument(
            "--result_from_suite",
            default="",
            choices=("", "vts", "cts", "gts", "sts"),
            help="To specify the type of a test suite report, since there can "
            "be multiple numbers of result sets from different test "
            "suites. If not specified, the HC will upload the report "
            "from last run suite and plan.")

    # @Override
    def Run(self, arg_line):
        """Upload args.src file to args.dest Google Cloud Storage."""
        args = self.arg_parser.ParseLine(arg_line)

        gsutil_path = build_provider_gcs.BuildProviderGCS.GetGsutilPath()
        if not gsutil_path:
            logging.error("Please check gsutil is installed and on your PATH")
            return False

        if args.src.startswith("latest-"):
            src_name = args.src[7:]
            if src_name in self.console.device_image_info:
                src_path = self.console.device_image_info[src_name]
            else:
                logging.error(
                    "Unable to find {} in device_image_info".format(src_name))
                return False
        else:
            try:
                src_paths = self.console.FormatString(args.src)
            except KeyError as e:
                logging.error("Unknown or uninitialized variable in src: %s",
                              e)
                return False

        src_path_list = src_paths.split(" ")
        for path in src_path_list:
            src_path = path.strip()
            if not os.path.isfile(src_path):
                logging.error("Cannot find a file: {}".format(src_path))
                return False

        try:
            dest_path = self.console.FormatString(args.dest)
        except KeyError as e:
            logging.error("Unknown or uninitialized variable in dest: %s", e)
            return False

        if not dest_path.startswith("gs://"):
            logging.error("{} is not correct GCS url.".format(dest_path))
            return False
        """ TODO(jongmok) : Before upload, login status, authorization,
                            and dest check are required. """
        copy_command = "{} cp {} {}".format(gsutil_path, src_paths, dest_path)
        _, stderr, err_code = cmd_utils.ExecuteOneShellCommand(copy_command)

        if err_code:
            logging.error(stderr)

        if args.report_path or args.clear_results:
            tools_path = ""
            if args.result_from_suite:
                tools_path = os.path.dirname(
                    self.console.test_suite_info[args.result_from_suite])
            else:
                try:
                    tools_path = os.path.dirname(self.console.test_suite_info[
                        self.console.FormatString("{suite_name}")])
                except KeyError:
                    logging.error(
                        "No test results found from any fetched test suite."
                        " Please fetch a test suite and run 'test' command,"
                        " then try running 'upload' command again.")
                    return False
            results_base_path = os.path.join(tools_path,
                                             common._RESULTS_BASE_PATH)

            if args.report_path:
                report_path = self.console.FormatString(args.report_path)
                if not report_path.startswith("gs://"):
                    logging.error(
                        "{} is not correct GCS url.".format(report_path))
                else:
                    self.UploadReport(gsutil_path, report_path, dest_path,
                                      results_base_path)

            if args.clear_results:
                shutil.rmtree(results_base_path, ignore_errors=True)

    def UploadReport(self, gsutil_path, report_path, log_path, results_path):
        """Uploads report summary file to the given path.

        Args:
            gsutil_path: string, the path of a gsutil binary.
            report_path: string, the dest GCS URL to which the summarized report
                                 file will be uploaded.
            log_path: string, GCS URL where the log files from the test run
                              have been uploaded.
            results_path: string, the base path for the results.
        """

        former_results = [
            result for result in os.listdir(results_path)
            if os.path.isdir(os.path.join(results_path, result))
            and not os.path.islink(os.path.join(results_path, result))
        ]

        if not former_results:
            logging.error("No test result found.")
            return False

        former_results.sort()
        latest_result = former_results[-1]
        latest_result_xml_path = os.path.join(results_path, latest_result,
                                              common._TEST_RESULT_XML)

        result_attrs = xml_utils.GetAttributes(
            latest_result_xml_path, common._RESULT_TAG, [
                common._SUITE_NAME_ATTR_KEY, common._SUITE_PLAN_ATTR_KEY,
                common._SUITE_VERSION_ATTR_KEY,
                common._SUITE_BUILD_NUM_ATTR_KEY,
                common._START_TIME_ATTR_KEY, common._END_TIME_ATTR_KEY,
                common._HOST_NAME_ATTR_KEY
            ])
        build_attrs = xml_utils.GetAttributes(
            latest_result_xml_path, common._BUILD_TAG, [
                common._SYSTEM_FINGERPRINT_ATTR_KEY,
                common._VENDOR_FINGERPRINT_ATTR_KEY
            ])
        summary_attrs = xml_utils.GetAttributes(
            latest_result_xml_path, common._SUMMARY_TAG, [
                common._PASSED_ATTR_KEY, common._FAILED_ATTR_KEY,
                common._MODULES_TOTAL_ATTR_KEY,
                common._MODULES_DONE_ATTR_KEY
            ])

        suite_res_msg = SuiteResMsg.TestSuiteResultMessage()
        suite_res_msg.result_path = log_path
        suite_res_msg.branch = self.console.FormatString("{branch}")
        suite_res_msg.target = self.console.FormatString("{target}")
        suite_res_msg.build_id = result_attrs[
            common._SUITE_BUILD_NUM_ATTR_KEY]
        suite_res_msg.suite_name = result_attrs[
            common._SUITE_NAME_ATTR_KEY]
        suite_res_msg.suite_plan = result_attrs[
            common._SUITE_PLAN_ATTR_KEY]
        suite_res_msg.suite_version = result_attrs[
            common._SUITE_VERSION_ATTR_KEY]
        suite_res_msg.suite_build_number = result_attrs[
            common._SUITE_BUILD_NUM_ATTR_KEY]
        suite_res_msg.start_time = long(
            result_attrs[common._START_TIME_ATTR_KEY])
        suite_res_msg.end_time = long(
            result_attrs[common._END_TIME_ATTR_KEY])
        suite_res_msg.host_name = result_attrs[common._HOST_NAME_ATTR_KEY]
        suite_res_msg.build_system_fingerprint = build_attrs[
            common._SYSTEM_FINGERPRINT_ATTR_KEY]
        suite_res_msg.build_vendor_fingerprint = build_attrs[
            common._VENDOR_FINGERPRINT_ATTR_KEY]
        suite_res_msg.passed_test_case_count = int(
            summary_attrs[common._PASSED_ATTR_KEY])
        suite_res_msg.failed_test_case_count = int(
            summary_attrs[common._FAILED_ATTR_KEY])
        suite_res_msg.modules_done = int(
            summary_attrs[common._MODULES_DONE_ATTR_KEY])
        suite_res_msg.modules_total = int(
            summary_attrs[common._MODULES_TOTAL_ATTR_KEY])

        report_file_path = os.path.join(
            self.console.tmp_logdir,
            self.console.FormatString("{timestamp_time}.bin"))
        with open(report_file_path, "w") as fd:
            fd.write(suite_res_msg.SerializeToString())
            fd.close()

        copy_command = "{} cp {} {}".format(
            gsutil_path, report_file_path,
            os.path.join(report_path, os.path.basename(report_file_path)))
        _, stderr, err_code = cmd_utils.ExecuteOneShellCommand(copy_command)
        if err_code:
            logging.error(stderr)
