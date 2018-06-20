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

import csv
import os
import logging
import re
import shutil
import tempfile
import zipfile

try:
    # TODO: Remove when we stop supporting Python 2
    import StringIO as string_io_module
except ImportError:
    import io as string_io_module

import gspread

from oauth2client.service_account import ServiceAccountCredentials

from host_controller import common
from host_controller.command_processor import base_command_processor
from host_controller.utils.gcp import gcs_utils
from host_controller.utils.parser import result_utils
from host_controller.utils.parser import xml_utils

# Texts on spreadsheet
_TABLE_HEADER = ("BITNESS", "TEST_MODULE", "TEST_CLASS", "TEST_CASE", "RESULT")

_CMP_TABLE_HEADER = _TABLE_HEADER + ("REFERENCE_RESULT",)

_TOO_MANY_DATA = "too many to be displayed"


class CommandSheet(base_command_processor.BaseCommandProcessor):
    """Command processor for sheet command.

    Attributes:
        _SCOPE: The scope needed to access Google Sheets.
        arg_parser: ConsoleArgumentParser object, argument parser.
        console: cmd.Cmd console object.
        command: string, command name which this processor will handle.
        command_detail: string, detailed explanation for the command.
    """
    _SCOPE = "https://www.googleapis.com/auth/drive"
    command = "sheet"
    command_detail = "Convert and upload a file to Google Sheets."

    # @Override
    def SetUp(self):
        """Initializes the parser for sheet command."""
        self.arg_parser.add_argument(
            "--src",
            required=True,
            help="The local file or GCS URL to be uploaded to Google Sheets. "
            "This command supports the results produced by TradeFed in XML "
            "and ZIP formats. Variables enclosed in {} are replaced with the "
            "the values stored in the console.")
        self.arg_parser.add_argument(
            "--dest",
            required=True,
            help="The ID of the spreadsheet to which the file is uploaded.")
        self.arg_parser.add_argument(
            "--ref",
            default=None,
            help="The reference file to be compared with src. If a test in "
            "src fails, its result in ref is also written to the spreadsheet.")
        self.arg_parser.add_argument(
            "--extra_rows",
            nargs="*",
            default=[],
            help="The extra rows written to the spreadsheet. Each argument "
            "is a row. Cells in a row are separated by commas.")
        self.arg_parser.add_argument(
            "--max",
            default=30000,
            type=int,
            help="Maximum number of results written to the spreadsheet. "
            "If there are too many results, only failing ones are written.")
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
            src_path = self.console.FormatString(args.src)
            ref_path = (None if args.ref is None else
                        self.console.FormatString(args.ref))
        except KeyError as e:
            logging.error(
                "Unknown or uninitialized variable in arguments: %s", e)
            return False

        if args.client_secrets is not None:
            credentials = ServiceAccountCredentials.from_json_keyfile_name(
                args.client_secrets, scopes=self._SCOPE)
        else:
            credentials = self.console.build_provider["pab"].Authenticate(
                scopes=self._SCOPE)
        client = gspread.authorize(credentials)

        # Load summary_attrs, src_dict, ref_dict, and exceed_max
        temp_dir = tempfile.mkdtemp()
        try:
            src_path = _GetResultAsXml(src_path, os.path.join(temp_dir, "src"))
            if not src_path:
                return False

            with open(src_path, "r") as src_file:
                summary_attrs = _ParseSummary(src_file)
                result_cnt = _GetResultCount(summary_attrs)
                show_pass = result_cnt >= 0 and result_cnt <= args.max

                src_file.seek(0)
                src_dict = _FilterTestResults(
                    src_file, args.max + 1,
                    lambda name, result: show_pass or result != "pass")

            exceed_max = len(src_dict) > args.max
            if src_dict and exceed_max:
                del src_dict[max(src_dict)]

            if ref_path:
                ref_path = _GetResultAsXml(
                    ref_path, os.path.join(temp_dir, "ref"))
                if not ref_path:
                    return False
                with open(ref_path, "r") as ref_file:
                    ref_dict = _FilterTestResults(
                        ref_file, args.max,
                        lambda name, result: src_dict.get(name, "") == "fail")
        finally:
            shutil.rmtree(temp_dir)

        # Output
        csv_file = string_io_module.StringIO()
        try:
            writer = csv.writer(csv_file, lineterminator="\n")

            writer.writerows(row.split(",") for row in args.extra_rows)
            writer.writerows(summary_attrs)

            src_list = sorted(src_dict.items())
            if ref_path:
                _WriteComparisonToCsv(src_list, ref_dict, writer)
            else:
                _WriteResultsToCsv(src_list, writer)

            if exceed_max:
                writer.writerow((_TOO_MANY_DATA,))

            client.import_csv(args.dest, csv_file.getvalue())
        finally:
            csv_file.close()


def _DownloadResultZipFromGcs(gcs_url, local_dir):
    """Downloads a result ZIP from GCS.

    If the GCS URL is a directory, this function searches the directory for the
    file whose name matches the pattern of result ZIP.

    Args:
        gcs_url: The URL of the ZIP file or the directory.
        local_dir: The local directory where the ZIP is downloaded.

    Returns:
        The path to the downloaded ZIP file.
        None if fail to download.
    """
    gsutil_path = gcs_utils.GetGsutilPath()
    if not gsutil_path:
        return False

    if gcs_utils.IsGcsFile(gsutil_path, gcs_url):
        gcs_urls = [gcs_url]
    else:
        ls_urls = gcs_utils.List(gsutil_path, gcs_url)
        gcs_urls = [x for x in ls_urls if
                    re.match(".+/results_\\d*\\.zip$", x)]
        if not gcs_urls:
            gcs_urls = [x for x in ls_urls if
                        re.match(".+/log-result_\\d*\\.zip$", x)]

    if not gcs_urls:
        logging.error("No results on %s", gcs_url)
        return None
    if len(gcs_urls) > 1:
        logging.warning("More than one result. Select %s", gcs_urls[0])

    if not os.path.exists(local_dir):
        os.makedirs(local_dir)
    if not gcs_utils.Copy(gsutil_path, gcs_urls[0], local_dir):
        logging.error("Fail to copy from %s", gcs_urls[0])
        return None

    return os.path.join(local_dir, gcs_urls[0].rpartition("/")[2])


def _GetResultAsXml(src, temp_dir):
    """Downloads and extracts an XML result.

    If src is a GCS URL, it is downloaded to temp_dir.
    If the file is a ZIP, it is extracted to temp_dir.

    Args:
        src: The location of the file, can be a directory on GCS,
             a ZIP file on GCS, a local ZIP file, or a local XML file.
        temp_dir: The directory where the ZIP is downloaded and extracted.

    Returns:
        The path to the XML file.
        None if fails to the find the XML.
    """
    original_src = src
    if src.startswith("gs://"):
        src = _DownloadResultZipFromGcs(src, os.path.join(temp_dir, "zipped"))
        if not src:
            return None

    if zipfile.is_zipfile(src):
        with zipfile.ZipFile(src, mode="r") as zip_file:
            src = result_utils.ExtractResultZip(
                zip_file, os.path.join(temp_dir, "unzipped"))
        if not src:
            logging.error("Cannot find XML result in %s", original_src)
            return None

    return src


def _ParseSummary(result_xml):
    """Gets test summary from an XML.

    Args:
        result_xml: The input file object in XML format.

    Returns:
        A list of (attribute_name, value).
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

    attr_list = []

    for attr_keys, attrs in (
            (result_attr_keys, result_attrs),
            (build_attr_keys, build_attrs),
            (summary_attr_keys, summary_attrs)):
        for attr_key in attr_keys:
            attr_list.append((attr_key, attrs.get(attr_key, "")))

    return attr_list


def _GetResultCount(attr_list):
    """Gets total number of results from a test summary.

    Args:
        attr_list: A list of (attribute_name, value).

    Returns:
        An integer, number of results.
        -1 if fails to parse the number.
    """
    try:
        pass_cnt = next(v for k, v in attr_list if
                        k == common._PASSED_ATTR_KEY)
        fail_cnt = next(v for k, v in attr_list if
                        k == common._FAILED_ATTR_KEY)
    except StopIteration:
        return -1

    try:
        return int(pass_cnt) + int(fail_cnt)
    except ValueError:
        return -1


def _FilterTestResults(xml_file, max_return, filter_func):
    """Converts a TradeFed report from XML to dictionary.

    Args:
        xml_file: The input file object in XML format.
        max_return: Maximum number of output results.
        filter_func: A function taking the test name and result as parameters,
                     and returning whether it should be included.

    Returns:
        A dict of {name: result} where name is a tuple of strings and result
        is a string.
    """
    result_dict = dict()
    for module, testcase, test in result_utils.IterateTestResults(xml_file):
        if len(result_dict) >= max_return:
            break
        test_name = result_utils.GetTestName(module, testcase, test)
        result = test.attrib.get(common._RESULT_ATTR_KEY, "")
        if filter_func(test_name, result):
            result_dict[test_name] = result

    return result_dict


def _WriteResultsToCsv(result_list, writer):
    """Writes a list of test names and results to a CSV file.

    Args:
        result_list: The list of (name, result).
        writer: The object of CSV writer.
    """
    writer.writerow(_TABLE_HEADER)
    writer.writerows(name + (result,) for name, result in result_list)


def _WriteComparisonToCsv(result_list, reference_dict, writer):
    """Writes test names, results, and reference results to a CSV file.

    Args:
        result_list: The list of (name, result).
        reference_dict: The dict of {name: reference_result}.
        writer: The object of CSV writer.
    """
    writer.writerow(_CMP_TABLE_HEADER)
    for name, result in result_list:
        if result == "fail":
            reference = reference_dict.get(name, "no_data")
        else:
            reference = ""
        writer.writerow(name + (result, reference))
