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
import logging
import shutil
import tempfile
import zipfile

try:
    # TODO: Remove when we stop supporting Python 2
    import StringIO as string_io_module
except ImportError:
    import io as string_io_module

from xml.etree import ElementTree

import gspread

from oauth2client.service_account import ServiceAccountCredentials

from host_controller import common
from host_controller.command_processor import base_command_processor
from host_controller.utils.parser import xml_utils


class CommandSheet(base_command_processor.BaseCommandProcessor):
    """Command processor for sheet command.

    Attributes:
        _SCOPE: The scope needed to access Google Sheets.
        _MAX_SPREADSHEET_RESULTS: Maximum number of results to be written to
                                  the spreadsheet. If the results are too many,
                                  only failing results are written.
        arg_parser: ConsoleArgumentParser object, argument parser.
        console: cmd.Cmd console object.
        command: string, command name which this processor will handle.
        command_detail: string, detailed explanation for the command.
    """
    _SCOPE = "https://www.googleapis.com/auth/drive"
    _MAX_SPREADSHEET_RESULTS = 30000
    command = "sheet"
    command_detail = "Convert and upload a file to Google Sheets."

    # @Override
    def SetUp(self):
        """Initializes the parser for sheet command."""
        self.arg_parser.add_argument(
            "--src",
            required=True,
            help="The file to be uploaded to Google Sheets. Currently this"
            "command supports only the XML and ZIP results produced by "
            "TradeFed. Variables enclosed in {} are replaced with the values "
            "stored in the console.")
        self.arg_parser.add_argument(
            "--dest",
            required=True,
            help="The ID of the spreadsheet to which the file is uploaded.")
        self.arg_parser.add_argument(
            "--extra_rows",
            nargs="*",
            default=[],
            help="The extra rows written to the spreadsheet. Each argument "
            "is a row. Cells in a row are separated by commas.")
        self.arg_parser.add_argument(
            "--client_secrets",
            default=None,
            help="The path to the client secrets file in JSON format for "
            "authentication. If this argument is not specified, this command "
            "uses PAB client secrets.")

    # @Override
    def Run(self, arg_line):
        """Uploads args.src file to args.dest on Google Sheets."""
        args = self.arg_parser.ParseLine(arg_line)

        try:
            src = self.console.FormatString(args.src)
        except KeyError as e:
            logging.error("Unknown or uninitialized variable in src: %s", e)
            return False

        if args.client_secrets is not None:
            credentials = ServiceAccountCredentials.from_json_keyfile_name(
                args.client_secrets, scopes=self._SCOPE)
        else:
            credentials = self.console.build_provider["pab"].Authenticate(
                scopes=self._SCOPE)
        client = gspread.authorize(credentials)

        csv_file = string_io_module.StringIO()
        try:
            for row in args.extra_rows:
                csv_file.write(row + "\n")

            if zipfile.is_zipfile(src):
                with zipfile.ZipFile(src, "r") as src_zip:
                    if not self._ConvertResultZipToCsv(src_zip, csv_file):
                        logging.error("Cannot find test results in %s", src)
                        return False
            else:
                with open(src, "r") as src_file:
                    self._ConvertResultXmlToCsv(src_file, csv_file)

            client.import_csv(args.dest, csv_file.getvalue())
        finally:
            csv_file.close()

    def _ConvertResultZipToCsv(self, zip_file, csv_file):
        """Converts a zipped TradeFed report to CSV.

        Args:
            zip_file: The input ZipFile containing the report in XML format.
            csv_file: The output file object in CSV format.

        Returns:
            A boolean, whether the XML file is found.
        """
        try:
            xml_name = next(x for x in zip_file.namelist() if
                            x.endswith("log-result.xml") or
                            x.endswith("test_result.xml"))
        except StopIteration:
            return False

        temp_dir = tempfile.mkdtemp()
        try:
            xml_path = zip_file.extract(xml_name, path=temp_dir)
            with open(xml_path, "rU") as xml_file:
                self._ConvertResultXmlToCsv(xml_file, csv_file)
        finally:
            shutil.rmtree(temp_dir)
        return True

    def _ConvertResultXmlToCsv(self, result_xml, csv_file):
        """Converts a TradeFed report from XML to CSV.

        Args:
            result_xml: The input file object in XML format.
            csv_file: The output file object in CSV format.
        """
        result_attr_keys = [
            common._SUITE_NAME_ATTR_KEY, common._SUITE_PLAN_ATTR_KEY,
            common._SUITE_VERSION_ATTR_KEY, common._SUITE_BUILD_NUM_ATTR_KEY,
            common._START_DISPLAY_TIME_ATTR_KEY,
            common._END_DISPLAY_TIME_ATTR_KEY
        ]
        build_attr_keys = [
            common._FINGERPRINT_ATTR_KEY,
            common._SYSTEM_FINGERPRINT_ATTR_KEY,
            common._VENDOR_FINGERPRINT_ATTR_KEY
        ]
        summary_attr_keys = [
            common._PASSED_ATTR_KEY, common._FAILED_ATTR_KEY,
            common._MODULES_TOTAL_ATTR_KEY, common._MODULES_DONE_ATTR_KEY
        ]
        result_xml.seek(0)
        result_attrs = xml_utils.GetAttributes(
            result_xml, common._RESULT_TAG, result_attr_keys)
        result_xml.seek(0)
        build_attrs = xml_utils.GetAttributes(
            result_xml, common._BUILD_TAG, build_attr_keys)
        result_xml.seek(0)
        summary_attrs = xml_utils.GetAttributes(
            result_xml, common._SUMMARY_TAG, summary_attr_keys)

        for attr_keys, attrs in (
                (result_attr_keys, result_attrs),
                (build_attr_keys, build_attrs),
                (summary_attr_keys, summary_attrs)):
            for attr_key in attr_keys:
                csv_file.write("%s,%s\n" % (attr_key, attrs.get(attr_key, "")))

        pass_cnt = summary_attrs.get(common._PASSED_ATTR_KEY, "")
        fail_cnt = summary_attrs.get(common._FAILED_ATTR_KEY, "")
        try:
            show_pass = (int(pass_cnt) + int(fail_cnt) <=
                         self._MAX_SPREADSHEET_RESULTS)
        except ValueError:
            show_pass = False

        write_cnt = 0
        module_name = ""
        testcase_name = ""
        test_name = ""
        csv_file.write("RESULT,TEST_MODULE,TEST_CLASS,TEST_CASE\n")
        result_xml.seek(0)
        for event, elem in ElementTree.iterparse(
                result_xml, events=("start", "end")):
            name = (elem.attrib.get(common._NAME_ATTR_KEY, "") if
                    event == "start" else "")
            if elem.tag == common._MODULE_TAG:
                module_name = name
            elif elem.tag == common._TESTCASE_TAG:
                testcase_name = name
            elif elem.tag == common._TEST_TAG:
                test_name = name

            if elem.tag == common._TEST_TAG and event == "start":
                result = elem.attrib.get(common._RESULT_ATTR_KEY, "")
                if not show_pass and result == "pass":
                    continue
                if write_cnt > self._MAX_SPREADSHEET_RESULTS:
                    continue
                if write_cnt == self._MAX_SPREADSHEET_RESULTS:
                    csv_file.write("too many to be displayed\n")
                    write_cnt += 1
                    continue
                csv_file.write("%s,%s,%s,%s\n" %
                               (result, module_name, testcase_name, test_name))
                write_cnt += 1
