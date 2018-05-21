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

from host_controller.command_processor import base_command_processor

from vts.utils.python.common import cmd_utils
from vts.utils.python.controllers import adb
from vts.utils.python.controllers import android_device


class CommandDUT(base_command_processor.BaseCommandProcessor):
    """Command processor for DUT command.

    Attributes:
        arg_parser: ConsoleArgumentParser object, argument parser.
        console: cmd.Cmd console object.
        command: string, command name which this processor will handle.
        command_detail: string, detailed explanation for the command.
    """

    command = "dut"
    command_detail = "Performs certain operations on DUT (Device Under Test)."

    # @Override
    def SetUp(self):
        """Initializes the parser for dut command."""
        self.arg_parser.add_argument(
            "--operation",
            choices=("wifi_on", "wifi_off"),
            default="",
            required=True,
            help="Operation to perform.")
        self.arg_parser.add_argument(
            "--serial",
            default="",
            required=True,
            help="The device serial.")
        self.arg_parser.add_argument(
            "--ap",
            default="",  # Required only for wifi_on
            help="Access point (AP) name for 'wifi_on' operation.")

    # @Override
    def Run(self, arg_line):
        """Performs the requested operation on the selected DUT."""
        args = self.arg_parser.ParseLine(arg_line)
        device = android_device.AndroidDevice(args.serial, device_callback_port=-1)
        device.waitForBootCompletion()
        adb_proxy = adb.AdbProxy(serial=args.serial)
        adb_proxy.root()
        try:
            if args.operation == "wifi_on":
                adb_proxy.shell("svc wifi enable")
                if args.ap:
                    adb_proxy.install("../testcases/DATA/app/WifiUtil/WifiUtil.apk")
                    adb_proxy.shell("am instrument -e method \"connectToNetwork\" "
                                    "-e ssid %s "
                                    "-w com.android.tradefed.utils.wifi/.WifiUtil" % args.ap)
            elif args.operation == "wifi_off":
                adb_proxy.shell("svc wifi disable")
        except adb.AdbError as e:
            logging.exception(e)
            return False
