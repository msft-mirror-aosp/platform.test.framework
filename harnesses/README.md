To release a new CTS TF prebuilt binary

`$ lunch aosp_arm64`
`$ make tradefed-cts`
`$ cp out/host/linux-x86/framework/tradefed-cts.jar test/framework/harnesses/cts-tradefed/tradefed-cts-prebuilt.jar`

To test a test suite which uses that prebuilt binary

`$ make vts -j32`

