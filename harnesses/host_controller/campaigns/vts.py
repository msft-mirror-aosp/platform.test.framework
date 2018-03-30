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

from host_controller import common
from vti.test_serving.proto import TestScheduleConfigMessage_pb2 as pb

# The list of the kwargs key. can retrieve informations on the leased job.
_JOB_ATTR_LIST = [
    "build_id",
    "test_name",
    "shards",
    "serial",
    "build_target",
    "manifest_branch",
    "gsi_branch",
    "gsi_build_target",
    "test_branch",
    "test_build_target",
]


def HasAttr(attr, **kwargs):
    """Returns True if 'attr' is in 'kwargs' as an arg."""
    return True if attr in kwargs and kwargs[attr] else False


def EmitConsoleCommands(**kwargs):
    """Runs a common VTS-on-GSI or CTS-on-GSI test.

    This uses a given device branch information and automatically
    selects a GSI branch and a test branch.
    """
    result = []

    if not set(_JOB_ATTR_LIST).issubset(kwargs):
        missing_keys = [key for key in _JOB_ATTR_LIST if key not in kwargs]
        logging.error("Leased job missing attribute(s): {}".format(
            ", ".join(missing_keys)))
        return None

    if isinstance(kwargs["build_target"], list):
        build_target = kwargs["build_target"][0]
    else:
        build_target = kwargs["build_target"]

    if HasAttr("pab_account_id", **kwargs):
        pab_account_id = kwargs["pab_account_id"]
    else:
        pab_account_id = common._DEFAULT_ACCOUNT_ID_INTERNAL

    manifest_branch = kwargs["manifest_branch"]
    build_id = kwargs["build_id"]
    build_storage_type = pb.BUILD_STORAGE_TYPE_PAB
    if HasAttr("build_storage_type", **kwargs):
        build_storage_type = int(kwargs["build_storage_type"])

    if build_storage_type == pb.BUILD_STORAGE_TYPE_PAB:
        result.append(
            "fetch --type=pab --branch=%s --target=%s --artifact_name=%s-img-%s.zip "
            "--build_id=%s --account_id=%s" %
            (manifest_branch, build_target, build_target.split("-")[0],
             build_id if build_id != "latest" else "{build_id}", build_id,
             pab_account_id))
        if HasAttr("require_signed_device_build", **kwargs):
            result[-1] += " --fetch_signed_build=True"

        result.append(
            "fetch --type=pab --branch=%s --target=%s --artifact_name=bootloader.img "
            "--build_id=%s --account_id=%s" % (manifest_branch, build_target,
                                               build_id, pab_account_id))

        result.append(
            "fetch --type=pab --branch=%s --target=%s --artifact_name=radio.img "
            "--build_id=%s --account_id=%s" % (manifest_branch, build_target,
                                               build_id, pab_account_id))
    elif build_storage_type == pb.BUILD_STORAGE_TYPE_GCS:
        result.append("fetch --type=gcs --path=%s" % (manifest_branch))
        if common.UNIVERSAL9810 in build_target:
            result[-1] += " --full_device_images=True"
    else:
        logging.error("unknown build storage type is given: %d",
                      build_storage_type)
        return None

    if HasAttr("gsi_branch", **kwargs):
        gsi = True
    else:
        gsi = False

    shards = int(kwargs["shards"])
    serials = kwargs["serial"]
    if gsi:
        if common.SDM845 in build_target:
            if shards > 1:
                sub_commands = []
                if shards <= len(serials):
                    for shard_index in range(shards):
                        sub_commands.append(
                            GenerateSdm845SetupCommands(serials[shard_index]))
                result.append(sub_commands)
            else:
                result.extend(GenerateSdm845SetupCommands(serials[0]))

        if HasAttr("gsi_build_id", **kwargs):
            gsi_build_id = kwargs["gsi_build_id"]
        else:
            gsi_build_id = "latest"
        gsi_storage_type = pb.BUILD_STORAGE_TYPE_PAB
        if HasAttr("gsi_storage_type", **kwargs):
            gsi_storage_type = int(kwargs["gsi_storage_type"])

        if gsi_storage_type == pb.BUILD_STORAGE_TYPE_PAB:
            result.append(
                "fetch --type=pab --branch=%s --target=%s "
                "--artifact_name=%s-img-{build_id}.zip --build_id=%s" %
                (kwargs["gsi_branch"], kwargs["gsi_build_target"],
                 kwargs["gsi_build_target"].split("-")[0], gsi_build_id))
        elif gsi_storage_type == pb.BUILD_STORAGE_TYPE_GCS:
            result.append("fetch --type=gcs --path=%s/%s-img-%s.zip" %
                          (kwargs["gsi_branch"],
                           kwargs["gsi_build_target"].split("-")[0],
                           gsi_build_id))
        else:
            logging.error("unknown gsi storage type is given: %d",
                          gsi_storage_type)
            return None

        if HasAttr("gsi_pab_account_id", **kwargs):
            result[-1] += " --account_id=%s" % kwargs["gsi_pab_account_id"]

    if HasAttr("test_build_id", **kwargs):
        test_build_id = kwargs["test_build_id"]
    else:
        test_build_id = "latest"
    test_storage_type = pb.BUILD_STORAGE_TYPE_PAB
    if HasAttr("test_storage_type", **kwargs):
        test_storage_type = int(kwargs["test_storage_type"])

    if test_storage_type == pb.BUILD_STORAGE_TYPE_PAB:
        result.append("fetch --type=pab --branch=%s --target=%s "
                      "--artifact_name=android-vts.zip --build_id=%s" %
                      (kwargs["test_branch"], kwargs["test_build_target"],
                       test_build_id))
    elif test_storage_type == pb.BUILD_STORAGE_TYPE_GCS:
        result.append("fetch --type=gcs --path=%s/%s.zip" %
                      (kwargs["test_branch"], kwargs["test_build_target"]))
    else:
        logging.error("unknown test storage type is given: %d",
                      test_storage_type)
        return None

    if HasAttr("test_pab_account_id", **kwargs):
        result[-1] += " --account_id=%s" % kwargs["test_pab_account_id"]

    result.append("info")
    if gsi:
        result.append("gsispl --version_from_path=boot.img")
        result.append("info")

    test_name = kwargs["test_name"].split("/")[-1]
    param = ""
    if HasAttr("param", **kwargs):
        param = " ".join(kwargs["param"])

    if shards > 1:
        sub_commands = []
        test_command = "test --keep-result -- %s --shards %d %s" % (test_name,
                                                                    shards,
                                                                    param)
        if shards <= len(serials):
            for shard_index in range(shards):
                new_cmd_list = []
                if common.SDM845 in build_target and gsi:
                    new_cmd_list.extend(
                        GenerateSdm845GsiFlashingCommands(
                            serials[shard_index]))
                elif common.UNIVERSAL9810 in build_target and gsi:
                    new_cmd_list.extend(
                        GenerateUniversal9810GsiFlashingCommands(
                            serials[shard_index]))
                else:
                    new_cmd_list.append(
                        "flash --current --serial %s --skip-vbmeta=True " %
                        serials[shard_index])
                new_cmd_list.append("adb -s %s root" % serials[shard_index])
                new_cmd_list.append(
                    "dut --operation=wifi_on --serial=%s --ap=%s" %
                    (serials[shard_index], common._DEFAULT_WIFI_AP))
                test_command += " --serial %s" % serials[shard_index]
                sub_commands.append(new_cmd_list)
        result.append(sub_commands)
        result.append(test_command)
    else:
        if common.SDM845 in build_target and gsi:
            result.extend(GenerateSdm845GsiFlashingCommands(serials[0]))
        elif common.UNIVERSAL9810 in build_target and gsi:
            result.extend(GenerateUniversal9810GsiFlashingCommands(serials[0]))
        else:
            result.append(
                "flash --current --serial %s --skip-vbmeta=True" % serials[0])
        result.append("dut --operation=wifi_on --serial=%s --ap=%s" %
                      (serials[0], common._DEFAULT_WIFI_AP))
        if serials:
            serial_arg_list = []
            for serial in serials:
                result.append("adb -s %s root" % serial)
                serial_arg_list.append("--serial %s" % serial)
            result.append("test --keep-result -- %s %s --shards %s %s" %
                          (test_name, " ".join(serial_arg_list), shards,
                           param))
        else:
            result.append("test --keep-result -- %s --shards %s %s" %
                          (test_name, shards, param))

    if "retry_count" in kwargs:
        retry_count = int(kwargs["retry_count"])
        retry_command = "retry --count %d" % retry_count
        if shards > 1:
            retry_command += " --shards %d" % shards
            for shard_index in range(shards):
                retry_command += " --serial %s" % serials[shard_index]
        else:
            retry_command += " --serial %s" % serials[0]
        result.append(retry_command)

    result.append(
        "upload --src={result_full} --dest=gs://vts-report/{suite_plan}"
        "/{branch}/{target}/%s_{build_id}_{timestamp}/" % build_target)

    return result


def GenerateSdm845SetupCommands(serial):
    """Returns a sequence of console commands to setup a device.

    Args:
        serial: string, the target device serial number.

    Returns:
        a list of strings, each string is a console command.
    """
    return [
        ("fastboot -s %s flash boot "
         "{device-image[full-zipfile-dir]}/boot.img" % serial),
        ("fastboot -s %s flash dtbo "
         "{device-image[full-zipfile-dir]}/dtbo.img" % serial),
        ("fastboot -s %s flash system "
         "{device-image[full-zipfile-dir]}/system.img" % serial),
        ("fastboot -s %s flash userdata "
         "{device-image[full-zipfile-dir]}/userdata.img" % serial),
        ("fastboot -s %s flash vbmeta "
         "{device-image[full-zipfile-dir]}/vbmeta.img "
         "-- --disable-verity" % serial),
        ("fastboot -s %s flash vendor "
         "{device-image[full-zipfile-dir]}/vendor.img" % serial),
        "fastboot -s %s reboot" % serial,
        "sleep 90",  # wait for boot_complete (success)
        "adb -s %s root" % serial,
        # TODO: to make sure {tmp_dir} is unique per session and
        #       is cleaned up at exit.
        "shell -- mkdir -p {tmp_dir}/%s" % serial,
        ("adb -s %s pull /system/lib64/libdrm.so "
         "{tmp_dir}/%s" % (serial, serial)),
        ("adb -s %s pull /system/lib64/vendor.display.color@1.0.so "
         "{tmp_dir}/%s" % (serial, serial)),
        ("adb -s %s pull /system/lib64/vendor.display.config@1.0.so "
         "{tmp_dir}/%s" % (serial, serial)),
        ("adb -s %s pull /system/lib64/vendor.display.config@1.1.so "
         "{tmp_dir}/%s" % (serial, serial)),
        ("adb -s %s pull /system/lib64/vendor.display.postproc@1.0.so "
         "{tmp_dir}/%s" % (serial, serial)),
        ("adb -s %s pull /system/lib64/vendor.qti.hardware.perf@1.0.so "
         "{tmp_dir}/%s" % (serial, serial)),
        "adb -s %s reboot bootloader" % serial,
        ("fastboot -s %s flash vbmeta "
         "{device-image[full-zipfile-dir]}/vbmeta.img "
         "-- --disable-verity" % serial),
    ]


def GenerateSdm845GsiFlashingCommands(serial):
    """Returns a sequence of console commands to flash GSI to a device.

    Args:
        serial: string, the target device serial number.

    Returns:
        a list of strings, each string is a console command.
    """
    return [
        "fastboot -s %s flash system {device-image[system.img]}" % serial,
        "fastboot -s %s -- -w reboot" % serial,
        "sleep 90",  # wait until adb shell (not boot complete)
        "adb -s %s root" % serial,
        "adb -s %s remount" % serial,
        "adb -s %s shell setenforce 0" % serial,
        "adb -s %s shell mkdir /bt_firmware" % serial,
        "adb -s %s shell chown system:system /bt_firmware" % serial,
        "adb -s %s shell chmod 650 /bt_firmware" % serial,
        "adb -s %s shell setenforce 1" % serial,
        ("adb -s %s shell ln -- -s /system/lib64/vndk-sp-P/libhidltransport.so "
         "/system/lib64/vndk-P/android.hidl.base@1.0.so" % serial),
        ("adb -s %s shell ln -- -s /system/lib/vndk-sp-P/libhidltransport.so "
         "/system/lib/vndk-P/android.hidl.base@1.0.so" % serial),
        "adb -s %s push libdrm.so /system/lib64" % serial,
        ("adb -s %s push {tmp_dir}/%s/vendor.display.color@1.0.so "
         "/system/lib64" % (serial, serial)),
        ("adb -s %s push {tmp_dir}/%s/vendor.display.config@1.0.so "
         "/system/lib64" % (serial, serial)),
        ("adb -s %s push {tmp_dir}/%s/vendor.display.config@1.1.so "
         "/system/lib64" % (serial, serial)),
        ("adb -s %s push {tmp_dir}/%s/vendor.display.postproc@1.0.so "
         "/system/lib64" % (serial, serial)),
        ("adb -s %s push {tmp_dir}/%s/vendor.qti.hardware.perf@1.0.so "
         "/system/lib64" % (serial, serial)),
        "adb -s %s reboot bootloader" % serial,
        "sleep 5",
        "fastboot -s %s  -- -w reboot" % serial,
        "sleep 300",  # wait for boot_complete (success)
    ]


def GenerateUniversal9810GsiFlashingCommands(serial):
    """Returns a sequence of console commands to flash device imgs and GSI.

    Args:
        serial: string, the target device serial number.

    Returns:
        a list of strings, each string is a console command.
    """
    return [
        ("fastboot -s %s flash el3_mon "
         "{device-image[full-zipfile-dir]}/el3_mon.img" % serial),
        ("fastboot -s %s flash epbl "
         "{device-image[full-zipfile-dir]}/epbl.img" % serial),
        ("fastboot -s %s flash bootloader "
         "{device-image[full-zipfile-dir]}/u-boot.img" % serial),
        ("fastboot -s %s flash dtb "
         "{device-image[full-zipfile-dir]}/dtb.img" % serial),
        ("fastboot -s %s flash dtbo "
         "{device-image[full-zipfile-dir]}/dtbo.img" % serial),
        ("fastboot -s %s flash kernel "
         "{device-image[full-zipfile-dir]}/kernel.img" % serial),
        ("fastboot -s %s flash ramdisk "
         "{device-image[full-zipfile-dir]}/ramdisk.img" % serial),
        ("fastboot -s %s flash vendor "
         "{device-image[full-zipfile-dir]}/vendor.img -- -S 300M" % serial),
        ("fastboot -s %s flash system "
         "{device-image[gsi-zipfile-dir]}/system.img -- -S 512M" % serial),
        ("fastboot -s %s reboot -- -w" % serial),
        "sleep 300",  # wait for boot_complete (success)
    ]
