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

# The list of the kwargs key. can retrieve informations on the leased job.
_JOB_ADDITIONAL_ATTR_LIST = [
    "build_target",
    "manifest_branch",
    "gsi_branch",
    "gsi_build_target",
    "gsi_pab_account_id",
    "test_branch",
    "test_build_target",
    "test_pab_account_id",
]


def EmitConsoleCommands(_build_id="latest",
                        _test_name="vts/vts",
                        _shards=1,
                        _serials=None,
                        **kwargs):
    """Runs a common VTS-on-GSI or CTS-on-GSI test.

    This uses a given device branch information and automatically
    selects a GSI branch and a test branch.
    """
    result = []

    if not set(_JOB_ADDITIONAL_ATTR_LIST).issubset(kwargs):
        missing_keys = [
            key for key in _JOB_ADDITIONAL_ATTR_LIST if key not in kwargs
        ]
        print("Leased job missing attribute(s): {}".format(
            ", ".join(missing_keys)))
        return None

    if isinstance(kwargs["build_target"], list):
        build_target = kwargs["build_target"][0]
    else:
        build_target = kwargs["build_target"]

    result.append(
        "fetch --type=pab --branch=%s --target=%s --artifact_name=%s-img-%s.zip "
        "--build_id=%s --account_id=541462473" %
        (kwargs["manifest_branch"], build_target, build_target.split("-")[0],
         _build_id if _build_id != "latest" else "{build_id}", _build_id), )
    result.append(
        "fetch --type=pab --branch=%s --target=%s --artifact_name=bootloader.img "
        "--build_id=%s --account_id=541462473" % (kwargs["manifest_branch"],
                                                  build_target, _build_id), )
    result.append(
        "fetch --type=pab --branch=%s --target=%s --artifact_name=radio.img "
        "--build_id=%s --account_id=541462473" % (kwargs["manifest_branch"],
                                                  build_target, _build_id), )

    result.append("fetch --type=pab --branch=%s --target=%s "
                  "--artifact_name=aosp_arm64_ab-img-{build_id}.zip "
                  "--build_id=latest --account_id=%s" %
                  (kwargs["gsi_branch"], kwargs["gsi_build_target"],
                   kwargs["gsi_pab_account_id"]), )
    result.append("fetch --type=pab --branch=%s --target=%s "
                  "--artifact_name=android-vts.zip "
                  "--build_id=latest --account_id=%s" %
                  (kwargs["test_branch"], kwargs["test_build_target"],
                   kwargs["test_pab_account_id"]), )

    shards = int(_shards)
    result.append("info")
    result.append("gsispl --version_from_path=boot.img")
    test_name = _test_name.split("/")[-1]
    if shards > 1:
        sub_commands = []
        if shards <= len(_serials):
            for shard_index in range(shards):
                new_cmd_list = []
                new_cmd_list.append(
                    "flash --current --serial %s" % _serials[shard_index])
                new_cmd_list.append("test -- %s --serial %s --shard-count %d "
                                    "--shard-index %d" %
                                    (test_name, _serials[shard_index], shards,
                                     shard_index))
                sub_commands.append(new_cmd_list)
        result.append(sub_commands)
    else:
        result.append("flash --current --serial %s" % _serials[0])
        if _serials:
            result.append("test %s -- --serial %s --shards %s" %
                          (test_name, ",".join(_serials), shards))
        else:
            result.append("test %s -- --shards %s" % (test_name, shards))

    return result
