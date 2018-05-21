#!/usr/bin/env python
#
# Copyright 2017 - The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import os
import datetime
import argparse
import json
import logging
import zipfile
import zlib

from host_controller import common
from host_controller.build import build_provider_ab
from host_controller.build import build_provider_pab
from vts.utils.python.common import cmd_utils


def ValidateValues(args):
    """Validate batch information and pre-process if needed

    Args:
        args : a dict containing batch process information
    Returns:
        True if successfully validated, False if not
    """
    try:
        args["startMonth"] = datetime.datetime.strptime(
            args["startMonth"], "%Y-%m")
        args["endMonth"] = datetime.datetime.strptime(args["endMonth"],
                                                      "%Y-%m")

        if not args["startMonth"] <= args["endMonth"]:
            logging.error(
                "startMonth should be earlier than or equals to endMonth")
            return False
    except ValueError:
        logging.error("Wrong value for startMonth/endMonth")
        return False
    try:
        args["days"] = map(int, args["days"].split(','))
        if not set(args["days"]) <= set([1, 5]):
            logging.error("days should be either 1 or 5")
            return False
    except ValueError:
        logging.error("Wrong value for days")
        return False

    if not args["build_provider"] in ["ab", "pab"]:
        logging.error("build_provider should be either \"ab\" or \"pab\"")
        return False

    return True


def StartBatch(values, output_path):
    """Start batch process to fetch images, change spl version, and archive

    Args:
        values : a dict containing batch process information
        output_path : a string, output path
    """
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    logging.info("\noutput path: {}\n".format(output_path))
    if "build_id" in values:
        build_id = values["build_id"]
    else:
        build_id = "latest"

    for target in values["targets"]:
        if values["build_provider"] == "ab":
            build_provider = build_provider_ab.BuildProviderAB()
            logging.info("Start downloading target:{} ...".format(target))
            device_images, _, _ = build_provider.Fetch(
                branch=values["branch"],
                target="{}-{}".format(target, values["build_variant"]),
                artifact_name="{}-img-{}.zip".format(target, "{build_id}"),
                build_id=build_id)
        else:
            build_provider = build_provider_pab.BuildProviderPAB()
            device_images, _, _ = build_provider.GetArtifact(
                account_id=common._DEFAULT_ACCOUNT_ID,
                branch=values["branch"],
                target="{}-{}".format(target, values["build_variant"]),
                artifact_name="{}-img-{}.zip".format(target, "{build_id}"),
                build_id=build_id,
                method="GET")
        if "system.img" in device_images:
            logging.info("Downloading completed. system.img path: {}".format(
                device_images["system.img"]))
        else:
            logging.error("Could not download system image.")
            continue

        outputs = []
        version_month = values["startMonth"]
        while True:
            for day in values["days"]:
                version = "{:04d}-{:02d}-{:02d}".format(
                    version_month.year, version_month.month, day)
                output = os.path.join(output_path, "system-{}-{}.img".format(
                    target, version))
                logging.info("Change SPL to {} ...".format(version))
                stdout, _, err_code = cmd_utils.ExecuteOneShellCommand(
                    "{} {} {} {}".format(
                        os.path.join(os.getcwd(), "..", "bin",
                                     "change_security_patch_ver.sh"),
                        device_images["system.img"], output, version))
                if not err_code:
                    outputs.append(output)
                else:
                    logging.error(stdout)
            version_month = version_month.replace(
                year=version_month.year + (version_month.month - 1) / 12,
                month=(version_month.month + 1) % 12)

            if version_month > values["endMonth"]:
                break

        if values["archive"] == "zip":
            zip_path = os.path.join(output_path,
                                    "system-{}.zip".format(target))
            logging.info("archive to {} ...".format(zip_path))
            with zipfile.ZipFile(
                    zip_path,
                    mode='w',
                    compression=zipfile.ZIP_DEFLATED,
                    allowZip64=True) as target:
                # writing each file one by one
                for file in outputs:
                    target.write(file, os.path.basename(file))
                    os.remove(file)
            logging.info("archive completed.")

        # Delete build provider so temp directory will be removed.
        del build_provider

    return 0


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--ab-key", required=True, help="Path to ab key JSON file.")
    parser.add_argument(
        "--batch",
        type=argparse.FileType('r'),
        help="JSON formatted batch file.")
    parser.add_argument("--output-path", required=True, help="Output path.")
    args = parser.parse_args()

    if os.path.exists(args.ab_key):
        os.environ["run_ab_key"] = os.path.abspath(args.ab_key)

    values = json.load(args.batch)
    if not ValidateValues(values):
        return 1

    return StartBatch(values, args.output_path)


if __name__ == '__main__':
    main()
