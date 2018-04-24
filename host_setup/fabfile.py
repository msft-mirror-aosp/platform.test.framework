#
# Copyright 2018 - The Android Open Source Project
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

import imp
import os
import time

from fabric.api import env
from fabric.api import run
from fabric.api import settings
from fabric.api import sudo
from fabric.contrib.files import contains
from fabric.context_managers import cd

_PIP_REQUIREMENTS_PATHS = [
    "test/vts/script/pip_requirements.txt",
    "test/framework/harnesses/host_controller/script/pip_requirements.txt"
]


def SetPassword(password):
    """Sets password for hosts to access through ssh and to run sudo commands

    usage: $ fab SetPassword:<password for hosts>

    Args:
        password: string, password for hosts.
    """
    env.password = password


def GetHosts(hosts_file_path):
    """Configures env.hosts to a given list of hosts.

    usage: $ fab GetHosts:<path to a source file contains hosts info>

    Args:
        hosts_file_path: string, path to a python file passed from command file
                         input.
    """
    hosts_module = imp.load_source('hosts_module', hosts_file_path)
    env.hosts = hosts_module.EmitHostList()


def SetupIptables(ip_address_file_path):
    """Configures iptables setting for all hosts listed.

    usage: $ fab SetupIptables:<path to a source file contains ip addresses of
             certified machines>

    Args:
        ip_address_file_path: string, path to a python file passed from command
                              file input.
    """
    ip_addresses_module = imp.load_source('ip_addresses_module',
                                          ip_address_file_path)
    ip_address_list = ip_addresses_module.EmitIPAddressList()

    sudo("apt-get install -y iptables-persistent")
    sudo("iptables -P INPUT ACCEPT")
    sudo("iptables -P FORWARD ACCEPT")
    sudo("iptables -F")

    for ip_address in ip_address_list:
        sudo(
            "iptables -A INPUT -p tcp -s %s --dport 22 -j ACCEPT" % ip_address)

    sudo("iptables -P INPUT DROP")
    sudo("iptables -P FORWARD DROP")
    sudo("iptables -A INPUT -p icmp -j ACCEPT")
    sudo("netfilter-persistent save")
    sudo("netfilter-persistent reload")


def SetupSudoers():
    """Append sudo rules for vtslab user.

    usage: $ fab SetupSudoers
    """
    if not contains("/etc/sudoers", "vtslab", use_sudo=True):
        sudo("echo '' | sudo tee -a /etc/sudoers")
        sudo("echo '# Let vtslab account have all authorization' | "
             "sudo tee -a /etc/sudoers")
        sudo("echo 'vtslab  ALL=(ALL:ALL) ALL' | sudo tee -a /etc/sudoers")


def SetupUSBPermission():
    """Sets up the USB permission for adb and fastboot.

    usage: $ fab SetupUSBPermission
    """
    sudo("curl --create-dirs -L -o /etc/udev/rules.d/51-android.rules -O -L "
         "https://raw.githubusercontent.com/snowdream/51-android/master/"
         "51-android.rules")
    sudo("chmod a+r /etc/udev/rules.d/51-android.rules")
    sudo("service udev restart")


def SetupPackages(ip_address_file_path=None):
    """Sets up the execution environment for vts `run` command.

    Need to temporarily open the ports for apt-get and pip commands.

    usage: $ fab SetupPackages

    Args:
        ip_address_file_path: string, path to a python file passed from command
                              file input. Will be passed to SetupIptables().
    """
    sudo("iptables -P INPUT ACCEPT")

    # todo : replace "kr.ubuntu." to "ubuntu" in /etc/apt/sources.list
    sudo("apt-get upgrade -y")
    sudo("apt-get update -y")
    sudo("apt-get install -y git-core gnupg flex bison gperf build-essential "
         "zip curl zlib1g-dev gcc-multilib g++-multilib x11proto-core-dev "
         "libx11-dev lib32z-dev ccache libgl1-mesa-dev libxml2-utils xsltproc "
         "unzip liblz4-tool")

    sudo("apt-get install -y android-tools-adb")
    sudo("usermod -aG plugdev $LOGNAME")

    SetupUSBPermission()

    sudo("apt-get update")
    sudo("apt-get install -y python2.7")
    sudo("apt-get install -y python-pip")
    run("pip install --upgrade pip")
    sudo("apt-get install -y python-virtualenv")

    sudo("apt-get install -y python-dev python-protobuf protobuf-compiler "
         "python-setuptools")

    for req_path in _PIP_REQUIREMENTS_PATHS:
        full_path = os.path.join(os.environ["ANDROID_BUILD_TOP"], req_path)
        pip_requirement_list = []
        try:
            requirements_fd = open(full_path, "r")
            lines = requirements_fd.readlines()
            for line in lines:
                req = line.rstrip()
                if req != "" and not req.startswith("#"):
                    pip_requirement_list.append(req)
        except IOError as e:
            print("%s: %s" % (e.strerror, full_path))
            return
        sudo("pip install %s" % " ".join(pip_requirement_list))

    sudo("pip install --upgrade protobuf")

    lsb_result = run("lsb_release -c -s")
    sudo("echo \"deb http://packages.cloud.google.com/apt cloud-sdk-%s "
         "main\" | sudo tee -a /etc/apt/sources.list.d/google-cloud-sdk.list" %
         lsb_result)
    sudo("curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | "
         "sudo apt-key add -")
    sudo("apt-get update && sudo apt-get install -y google-cloud-sdk")
    sudo("apt-get install -y google-cloud-sdk-app-engine-java "
         "google-cloud-sdk-app-engine-python kubectl")

    sudo("apt-get install -y m4 bison")

    if ip_address_file_path is not None:
        SetupIptables(ip_address_file_path)


def DeployVtslab(vtslab_package_gcs_url=None):
    """Deploys vtslab package.

    Fetches and deploy vtlab by going through the processes described below
    1. Send the "exit --wait_for_jobs=True" command to all detached screen.
       And let the screen to terminate itself.
    2. Create a new screen instance that downloads and runs the new HC,
       give password and device command to the HC without actually attaching it

    usage: $ fab DeployVtslab -p <password> -H hosts.py -f <gs://vtslab-release/...>

    Args:
        vtslab_package_gcs_url: string, URL to a certain vtslab package file.
    """
    if not vtslab_package_gcs_url:
        print("Please specify vtslab package file URL using -f option.")
        return
    elif not vtslab_package_gcs_url.startswith("gs://vtslab-release/"):
        print("Please spcify a valid URL for the vtslab package.")
        return
    else:
        vti = "vtslab-schedule-" + vtslab_package_gcs_url[len(
            "gs://vtslab-release/"):].split("/")[0] + ".appspot.com"
    with settings(warn_only=True):
        screen_list_result = run("screen -list")
    lines = screen_list_result.split("\n")
    for line in lines:
        if "(Detached)" in line:
            screen_name = line.split("\t")[1]
            print(screen_name)
            with settings(warn_only=True):
                run("screen -S %s -X stuff \"exit --wait_for_jobs=True\"" %
                    screen_name)
                run("screen -S %s -X stuff \"^M\"" % screen_name)
                run("screen -S %s -X stuff \"exit\"" % screen_name)
                run("screen -S %s -X stuff \"^M\"" % screen_name)

    vtslab_package_file_name = os.path.basename(vtslab_package_gcs_url)
    run("mkdir -p ~/run/%s.dir/" % vtslab_package_file_name)
    with cd("~/run/%s.dir" % vtslab_package_file_name):
        run("gsutil cp %s ./" % vtslab_package_gcs_url)
        run("unzip -o %s" % vtslab_package_file_name)
    with cd("~/run/%s.dir/android-vtslab/tools" % vtslab_package_file_name):
        new_screen_name = run("cat ../testcases/version.txt")

    with cd("~/run/%s.dir/android-vtslab/tools" % vtslab_package_file_name):
        run("./make_screen %s" % new_screen_name)
    run("screen -S %s -X stuff \"./run --vti=%s\"" % (new_screen_name, vti))
    run("screen -S %s -X stuff \"^M\"" % new_screen_name)
    time.sleep(5)
    run("screen -S %s -X stuff \"password\"" % new_screen_name)
    run("screen -S %s -X stuff \"^M\"" % new_screen_name)
    run("screen -S %s -X stuff \"%s\"" % (new_screen_name, env.password))
    run("screen -S %s -X stuff \"^M\"" % new_screen_name)
    run("screen -S %s -X stuff \"device --lease=True\"" % new_screen_name)
    run("screen -S %s -X stuff \"^M\"" % new_screen_name)

    with cd("~/run/%s.dir" % vtslab_package_file_name):
        run("rm %s" % vtslab_package_file_name)
