#!/bin/bash
. build/envsetup.sh
lunch aosp_arm64
make WifiUtil -j
mkdir -p out/host/linux-x86/vtslab/android-vtslab/testcases/DATA/app
cp out/target/product/generic_arm64/testcases/WifiUtil/ out/host/linux-x86/vtslab/android-vtslab/testcases/DATA/app/ -rf
make vtslab -j
