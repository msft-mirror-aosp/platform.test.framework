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
import datetime
import threading

from host_controller import common
from host_controller.command_processor import base_command_processor


class CommandRelease(base_command_processor.BaseCommandProcessor):
    """Command processor for update command.

    Attributes:
        arg_parser: ConsoleArgumentParser object, argument parser.
        console: cmd.Cmd console object.
        command: string, command name which this processor will handle.
        command_detail: string, detailed explanation for the command.
        _timers: dict, instances of scheduled threading.Timer.
                 Uses timestamp("%H:%M") string as a key.
    """

    command = "release"
    command_detail = "Release HC. Used for fetching HC package from PAB and uploading to GCS."

    # @Override
    def SetUp(self):
        """Initializes the parser for update command."""
        self._timers = {}
        self.arg_parser.add_argument(
            "--schedule-for",
            default="17:00",
            help="Schedule to update HC package at the given time every day. "
            "Example: --schedule-for=%H:%M")
        self.arg_parser.add_argument(
            "--account_id",
            default=common._DEFAULT_ACCOUNT_ID,
            help="Partner Android Build account_id to use.")
        self.arg_parser.add_argument(
            "--branch", help="Branch to grab the artifact from.")
        self.arg_parser.add_argument(
            "--target",
            help="a comma-separate list of build target product(s).")
        self.arg_parser.add_argument(
            "--dest",
            help="Google Cloud Storage URL to which the file is uploaded.")
        self.arg_parser.add_argument(
            "--cancel", help="Cancel all scheduled release if given.")
        self.arg_parser.add_argument(
            "--print-all", help="Print all scheduled timers.")

    # @Override
    def Run(self, arg_line):
        """Schedule a host_constroller package release at a certain time."""
        args = self.arg_parser.ParseLine(arg_line)

        if args.print_all:
            print(self._timers)
            return

        if not args.cancel:
            if args.schedule_for == "now":
                self.ReleaseCallback(args.schedule_for, args.account_id,
                                     args.branch, args.target, args.dest)
                return

            elif len(args.schedule_for.split(":")) != 2:
                print("The format of --schedule-for flag is %H:%M")
                return False

            if (int(args.schedule_for.split(":")[0]) not in range(24)
                    or int(args.schedule_for.split(":")[-1]) not in range(60)):
                print("The value of --schedule-for flag must be in "
                      "\"00:00\"..\"23:59\" inclusive")
                return False

            if not args.schedule_for in self._timers:
                delta_time = datetime.datetime.now().replace(
                    hour=int(args.schedule_for.split(":")[0]),
                    minute=int(args.schedule_for.split(":")[-1]),
                    second=0,
                    microsecond=0) - datetime.datetime.now()

                if delta_time <= datetime.timedelta(0):
                    delta_time += datetime.timedelta(days=1)

                self._timers[args.schedule_for] = threading.Timer(
                    delta_time.total_seconds(), self.ReleaseCallback,
                    (args.schedule_for, args.account_id, args.branch,
                     args.target, args.dest))
                self._timers[args.schedule_for].daemon = True
                self._timers[args.schedule_for].start()
                print("Release job scheduled for {}".format(
                    datetime.datetime.now() + delta_time))
        else:
            self.CancelAllEvents()

    def FetchVtslab(self, account_id, branch, target):
        """Fetchs android-vtslab.zip and return the fetched file path.

        Args:
            account_id: string, Partner Android Build account_id to use.
            branch: string, branch to grab the artifact from.
            targets: string, a comma-separate list of build target product(s).

        Returns:
            path to the fetched android-vtslab.zip file. None if the fetching
            has failed.
        """
        self.console.build_provider["pab"].Authenticate()
        return self.console.build_provider["pab"].FetchLatestBuiltHCPackage(
            account_id, branch, target)

    def UploadVtslab(self, package_file_path, dest_path):
        """upload repackaged vtslab package to GCS.

        Args:
            package_file_path: string, path to the vtslab package file.
            dest_path: string, URL to GCS.
        """
        if dest_path and dest_path.endswith("/"):
            split_list = os.path.basename(package_file_path).split(".")
            split_list[0] += "-{timestamp_date}"
            dest_path += ".".join(split_list)

        upload_command = "upload --src %s --dest %s" % (package_file_path,
                                                        dest_path)
        self.console.onecmd(upload_command)

    def ReleaseCallback(self, schedule_for, account_id, branch, target, dest):
        """Target function for the scheduled Timer.

        Args:
            schedule_for: string, scheduled time for this Timer.
                          Format: "%H:%M" (from "00:00" to  "23:59" inclusive)
            account_id: string, Partner Android Build account_id to use.
            branch: string, branch to grab the artifact from.
            targets: string, a comma-separate list of build target product(s).
            dest: string, URL to GCS.
        """
        fetched_path = self.FetchVtslab(account_id, branch, target)
        if fetched_path:
            self.UploadVtslab(fetched_path, dest)

        if schedule_for != "now":
            delta_time = datetime.datetime.now().replace(
                hour=int(schedule_for.split(":")[0]),
                minute=int(schedule_for.split(":")[-1]),
                second=0,
                microsecond=0) - datetime.datetime.now() + datetime.timedelta(
                    days=1)
            self._timers[schedule_for] = threading.Timer(
                delta_time.total_seconds(), self.ReleaseCallback,
                (schedule_for, account_id, branch, target, dest))
            self._timers[schedule_for].daemon = True
            self._timers[schedule_for].start()
            print("Release job scheduled for {}".format(
                datetime.datetime.now() + delta_time))

    def CancelAllEvents(self):
        """Cancel all scheduled Timer."""
        for scheduled_time in self._timers:
            self._timers[scheduled_time].cancel()
        self._timers = {}
