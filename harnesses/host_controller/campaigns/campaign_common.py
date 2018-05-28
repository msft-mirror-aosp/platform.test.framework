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


def GetVersion(branch):
    """Returns the API level (integer) for the given branch."""
    branch = str(branch.lower())
    if branch.startswith("git_"):
        branch = branch[4:]
    if branch.startswith("aosp-"):
        branch = branch[5:]

    if "-treble-" in branch:
        branch = branch.replace("-treble-", "-")

    if branch.endswith("-dev"):
        branch = branch[:-4]
    elif branch.endswith("-release"):
        branch = branch[:-8]

    if (branch.startswith("o") and branch.endswith(
        ("mr1", "m2", "m3", "m4", "m5", "m6"))):
        return 8.1
    elif branch.startswith("o"):
        return 8.0
    elif branch.startswith("p"):
        return 9.0
    elif branch.startswith("gs://"):
        if "v8.0" in branch:
            return 8.0
        elif "v8.1" in branch:
            return 8.1
        elif "v9.0" in branch:
            return 9.0
    return 9.0


def EmitFetchCommands(**kwargs):
    """Returns a list of common fetch commands.

    This uses a given device branch information and automatically
    selects a GSI branch and a test branch.

    Args:
        kwargs: keyword argument, contains data about the leased job.
    Returns:
        list of command string.
        bool, True if GSI image is fetched. False otherwise
    """
    result = []
    if isinstance(kwargs["build_target"], list):
        build_target = kwargs["build_target"][0]
    else:
        build_target = kwargs["build_target"]
    shards = int(kwargs["shards"])
    suite_name, _ = kwargs["test_name"].split("/")
    serials = kwargs["serial"]

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
        if common.UNIVERSAL9810 in build_target:
            result[-1] += " --full_device_images=True"

        if HasAttr("has_bootloader_img", **kwargs):
            result.append("fetch --type=pab --branch=%s --target=%s "
                          "--artifact_name=bootloader.img --build_id=%s "
                          "--account_id=%s" % (manifest_branch, build_target,
                                               build_id, pab_account_id))

        if HasAttr("has_radio_img", **kwargs):
            result.append("fetch --type=pab --branch=%s --target=%s "
                          "--artifact_name=radio.img --build_id=%s "
                          "--account_id=%s" % (manifest_branch, build_target,
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

    if HasAttr("gsi_vendor_version", **kwargs):
        gsi_vendor_version = kwargs["gsi_vendor_version"]
    else:
        gsi_vendor_version = None

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
                "fetch --type=pab --branch=%s --target=%s --gsi=True "
                "--artifact_name=%s-img-{build_id}.zip --build_id=%s" %
                (kwargs["gsi_branch"], kwargs["gsi_build_target"],
                 kwargs["gsi_build_target"].split("-")[0], gsi_build_id))
        elif gsi_storage_type == pb.BUILD_STORAGE_TYPE_GCS:
            result.append("fetch --type=gcs --path=%s/%s-img-%s.zip "
                          "--gsi=True" %
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
                      "--artifact_name=android-%s.zip --build_id=%s" %
                      (kwargs["test_branch"], kwargs["test_build_target"],
                       suite_name, test_build_id))
    elif test_storage_type == pb.BUILD_STORAGE_TYPE_GCS:
        result.append("fetch --type=gcs --path=%s/%s.zip --set_suite_as=%s" %
                      (kwargs["test_branch"], kwargs["test_build_target"],
                       suite_name))
    else:
        logging.error("unknown test storage type is given: %d",
                      test_storage_type)
        return None

    if HasAttr("test_pab_account_id", **kwargs):
        result[-1] += " --account_id=%s" % kwargs["test_pab_account_id"]

    result.append("info")
    if gsi:
        gsispl_command = "gsispl --version_from_path=boot.img"
        if gsi_vendor_version:
            gsispl_command += " --vendor_version=%s" % gsi_vendor_version
        result.append(gsispl_command)
        result.append("info")

    return result, gsi


def EmitFlashCommands(gsi, **kwargs):
    """Returns a list of common flash commands.

    This uses a given device branch information and automatically
    selects a GSI branch and a test branch.

    Args:
        gsi: bool, whether to flash GSI over vendor images or not.
        kwargs: keyword argument, contains data about the leased job.
    Returns:
        list of command string.
    """
    result = []
    result.append("repack")
    if HasAttr("image_package_repo_base", **kwargs):
        result[-1] += " --dest=%s" % kwargs["image_package_repo_base"]

    if isinstance(kwargs["build_target"], list):
        build_target = kwargs["build_target"][0]
    else:
        build_target = kwargs["build_target"]
    shards = int(kwargs["shards"])
    serials = kwargs["serial"]

    if shards > 1:
        sub_commands = []

        if shards <= len(serials):
            for shard_index in range(shards):
                new_cmd_list = []
                if common.K39TV1_BSP in build_target:
                    new_cmd_list.extend(
                        GenerateMt6739GsiFlashingCommands(
                            serials[shard_index], gsi))
                elif common.SDM845 in build_target and gsi:
                    new_cmd_list.extend(
                        GenerateSdm845GsiFlashingCommands(
                            serials[shard_index]))
                elif common.UNIVERSAL9810 in build_target:
                    new_cmd_list.extend(
                        GenerateUniversal9810GsiFlashingCommands(
                            serials[shard_index], gsi))
                else:
                    new_cmd_list.append(
                        "flash --current --serial %s --skip-vbmeta=True " %
                        serials[shard_index])
                new_cmd_list.append("adb -s %s root" % serials[shard_index])
                if common.SDM845 not in build_target:  # b/78487061
                    new_cmd_list.append(
                        "dut --operation=wifi_on --serial=%s --ap=%s" %
                        (serials[shard_index], common._DEFAULT_WIFI_AP))
                sub_commands.append(new_cmd_list)
        result.append(sub_commands)
    else:
        if common.K39TV1_BSP in build_target:
            result.extend(GenerateMt6739GsiFlashingCommands(serials[0], gsi))
        elif common.SDM845 in build_target and gsi:
            result.extend(GenerateSdm845GsiFlashingCommands(serials[0]))
        elif common.UNIVERSAL9810 in build_target:
            result.extend(
                GenerateUniversal9810GsiFlashingCommands(serials[0], gsi))
        else:
            result.append(
                "flash --current --serial %s --skip-vbmeta=True" % serials[0])
        if common.SDM845 not in build_target:  # b/78487061
            result.append("dut --operation=wifi_on --serial=%s --ap=%s" %
                          (serials[0], common._DEFAULT_WIFI_AP))
        if serials:
            serial_arg_list = []
            for serial in serials:
                result.append("adb -s %s root" % serial)
                serial_arg_list.append("--serial %s" % serial)

    return result


def EmitCommonConsoleCommands(**kwargs):
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
    shards = int(kwargs["shards"])
    suite_name, plan_name = kwargs["test_name"].split("/")
    serials = kwargs["serial"]

    fetch_commands_result, gsi = EmitFetchCommands(**kwargs)
    result.extend(fetch_commands_result)
    flash_commands_result = EmitFlashCommands(gsi, **kwargs)
    result.extend(flash_commands_result)

    param = ""
    if HasAttr("param", **kwargs):
        param = " ".join(kwargs["param"])

    test_branch = kwargs["test_branch"]
    if (GetVersion(test_branch) >= 9.0
            and (suite_name == "cts" or plan_name.startswith("cts"))):
        shard_option = "--shard-count"
        retry_option = "--retry_plan=%s-retry" % plan_name
    else:
        shard_option = "--shards"
        retry_option = ""

    if shards > 1:
        test_command = "test --suite %s --keep-result -- %s %s %d %s" % (
            suite_name, plan_name, shard_option, shards, param)
        if shards <= len(serials):
            for shard_index in range(shards):
                test_command += " --serial %s" % serials[shard_index]
        result.append(test_command)
    else:
        if serials:
            serial_arg_list = []
            for serial in serials:
                serial_arg_list.append("--serial %s" % serial)
            result.append("test --suite %s --keep-result -- %s %s %s" %
                          (suite_name, plan_name, " ".join(serial_arg_list),
                           param))
        else:
            result.append("test --suite %s --keep-result -- %s %s" %
                          (suite_name, plan_name, param))

    if "retry_count" in kwargs:
        retry_count = int(kwargs["retry_count"])
        retry_command = ("retry --suite %s --count %d %s" %
                         (suite_name, retry_count, retry_option))
        if shards > 1:
            retry_command += " %s %d" % (shard_option, shards)
            for shard_index in range(shards):
                retry_command += " --serial %s" % serials[shard_index]
        else:
            retry_command += " --serial %s" % serials[0]
        if suite_name == "cts" or plan_name == "cts-on-gsi":
            if common.SDM845 in build_target:
                # TODO(vtslab-dev): remove after b/77664643 is resolved
                pass
            else:
                retry_command += " --cleanup_devices=True"
        result.append(retry_command)

    if HasAttr("test_build_id", **kwargs):
        test_build_id = kwargs["test_build_id"]
    else:
        test_build_id = "latest"
    test_storage_type = pb.BUILD_STORAGE_TYPE_PAB
    if HasAttr("test_storage_type", **kwargs):
        test_storage_type = int(kwargs["test_storage_type"])

    if HasAttr("report_bucket", **kwargs):
        report_buckets = kwargs["report_bucket"]
    else:
        report_buckets = ["gs://vts-report"]

    upload_dests = []
    upload_commands = []
    for report_bucket in report_buckets:
        if test_storage_type == pb.BUILD_STORAGE_TYPE_PAB:
            upload_dest = ("%s/{suite_plan}/%s/{branch}/{target}/"
                           "%s_{build_id}_{timestamp}/" %
                           (report_bucket, plan_name, build_target))
        elif test_storage_type == pb.BUILD_STORAGE_TYPE_GCS:
            upload_dest = ("%s/{suite_plan}/%s/%s/%s/%s_%s_{timestamp}/" %
                           (report_bucket, plan_name,
                            kwargs["test_branch"].replace("gs://", "gs_")
                            if kwargs["test_branch"].startswith("gs://") else
                            kwargs["test_branch"], kwargs["test_build_target"],
                            build_target, test_build_id))
        upload_dests.append(upload_dest)
        upload_commands.append(
            "upload --src={result_full} --dest=%s "
            "--report_path=%s/suite_result/{timestamp_year}/{timestamp_month}/"
            "{timestamp_day}" % (upload_dest, report_bucket))

    if len(upload_commands) > 0:
        upload_commands[-1] += " --clear_results=True"

    extra_rows = " ".join("logs," + x for x in upload_dests)
    if HasAttr("report_spreadsheet_id", **kwargs):
        for sheet_id in kwargs["report_spreadsheet_id"]:
            result.append("sheet --src {result_zip} --dest %s "
                          "--extra_rows %s" % (sheet_id, extra_rows))

    result.extend(upload_commands)

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
        # removed -w from below command
        "fastboot -s %s -- reboot" % serial,
        "sleep 90",  # wait until adb shell (not boot complete)
        "adb -s %s root" % serial,
        "adb -s %s remount" % serial,
        "adb -s %s shell setenforce 0" % serial,
        "adb -s %s shell mkdir /bt_firmware" % serial,
        "adb -s %s shell chown system:system /bt_firmware" % serial,
        "adb -s %s shell chmod 650 /bt_firmware" % serial,
        "adb -s %s shell setenforce 1" % serial,
        ("adb -s %s push {tmp_dir}/%s/libdrm.so "
         "/system/lib64" % (serial, serial)),
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
        # removed -w from below command
        "fastboot -s %s  -- reboot" % serial,
        "sleep 300",  # wait for boot_complete (success)
    ]


def GenerateMt6739GsiFlashingCommands(serial, gsi=False):
    """Returns a sequence of console commands to flash device imgs and GSI.

    Args:
        serial: string, the target device serial number.
        gsi: bool, whether to flash GSI over vendor images or not.

    Returns:
        a list of strings, each string is a console command.
    """
    flash_img_cmd = ("fastboot -s %s flash %s "
                     "{device-image[full-zipfile-dir]}/%s")
    flash_gsi_cmd = ("fastboot -s %s flash system "
                     "{device-image[gsi-zipfile-dir]}/system.img")
    result = [
        flash_img_cmd % (serial, partition, image)
        for partition, image in (
            ("lk", "lk.img"),
            ("md1img", "md1img.img"),
            ("md1dsp", "md1dsp.img"),
            ("preloader", "preloader_k39tv1_bsp.bin"),
            ("recovery", "recovery.img"),
            ("spmfw", "spmfw.img"),
            ("mcupmfw", "mcupmfw.img"),
            ("lk2", "lk.img"),
            ("loader_ext1", "loader_ext.img"),
            ("loader_ext2", "loader_ext.img"),
            ("boot", "boot.img"),
            ("logo", "logo.bin"),
            ("odmdtbo", "odmdtbo.img"),
            ("tee1", "tee.img"),
            ("tee2", "tee.img"),
            ("vendor", "vendor.img"),
            ("cache", "cache.img"),
            ("userdata", "userdata.img"),
        )
    ]

    if gsi:
        result.append(flash_gsi_cmd % serial)
        result.append("fastboot -s %s -- -w" % serial)
    else:
        result.append(flash_img_cmd % (serial, "system", "system.img"))

    result.append("fastboot -s %s reboot" % serial)
    result.append("sleep 300")  # wait for boot_complete (success)

    return result


def GenerateUniversal9810GsiFlashingCommands(serial, gsi=False):
    """Returns a sequence of console commands to flash device imgs and GSI.

    Args:
        serial: string, the target device serial number.
        gsi: bool, whether to flash GSI over vendor images or not.

    Returns:
        a list of strings, each string is a console command.
    """
    result = [
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
    ]
    if gsi:
        result.append(
            ("fastboot -s %s flash system "
             "{device-image[gsi-zipfile-dir]}/system.img -- -S 512M" % serial))
    else:
        result.append((
            "fastboot -s %s flash system "
            "{device-image[full-zipfile-dir]}/system.img -- -S 512M" % serial))
    result.append("fastboot -s %s reboot -- -w" % serial)
    result.append("sleep 300")  # wait for boot_complete (success)

    return result


FLASH_COMMAND_EMITTER = {
    common.K39TV1_BSP: GenerateMt6739GsiFlashingCommands,
    common.SDM845: GenerateSdm845SetupCommands,
    common.UNIVERSAL9810: GenerateUniversal9810GsiFlashingCommands,
}
