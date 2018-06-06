# Based on JobModel defined in
# test/vti/test_serving/gae/webapp/src/proto/model.py

input_data = {
            "test_type": 1,
            "hostname": "my_hostname",
            "priority": "low",
            "test_name": "vts/vts",
            "require_signed_device_build": True,
            "has_bootloader_img": True,
            "has_radio_img": True,
            "device": "my_device",
            "serial": ["my_serial1", "my_serial2", "my_serial3"],

            # device image information
            "build_storage_type": 1,
            "manifest_branch": "my_branch",
            "build_target": "my_build_target",
            "build_id": "my_build_id",
            "pab_account_id": "my_pab_account_id",

            "shards": 3,
            "param": "",
            "status": 1,
            "period": 24 * 60,  # 1 day
        
            # GSI information
            "gsi_storage_type": 1,
            "gsi_branch": "my_gsi_branch",
            "gsi_build_target": "my_gsi_build_target",
            "gsi_build_id": "my_gsi_build_id",
            "gsi_pab_account_id": "my_gsi_pab_account_id",
            # gsi_vendor_version: "8.1.0"

            # test suite information
            "test_storage_type": 1,
            "test_branch": "my_test_branch",
            "test_build_target": "my_test_build_target",
            "test_build_id": "my_test_build_id",
            "test_pab_account_id": "my_test_pab_account_id",

            #timestamp = ndb.DateTimeProperty(auto_now=False)
            #heartbeat_stamp = ndb.DateTimeProperty(auto_now=False)
            "retry_count": 3,

            "infra_log_url": "infra_log_url",
        
            #parent_schedule = ndb.KeyProperty(kind="ScheduleModel")
        
            "image_package_repo_base": "image_package_repo_base",
        
            "report_bucket": ["report_bucket"],
            "report_spreadsheet_id": ["report_spreadsheet_id"],
        }

expected_output = [
  'fetch --type=pab --branch=my_branch --target=my_build_target --artifact_name=my_build_target-img-my_build_id.zip --build_id=my_build_id --account_id=my_pab_account_id --fetch_signed_build=True',
  'fetch --type=pab --branch=my_branch --target=my_build_target --artifact_name=bootloader.img --build_id=my_build_id --account_id=my_pab_account_id',
  'fetch --type=pab --branch=my_branch --target=my_build_target --artifact_name=radio.img --build_id=my_build_id --account_id=my_pab_account_id',
  'fetch --type=pab --branch=my_gsi_branch --target=my_gsi_build_target --gsi=True --artifact_name=my_gsi_build_target-img-{build_id}.zip --build_id=my_gsi_build_id --account_id=my_gsi_pab_account_id',
  'fetch --type=pab --branch=my_test_branch --target=my_test_build_target --artifact_name=android-vts.zip --build_id=my_test_build_id --account_id=my_test_pab_account_id',
  'info',
  'gsispl --version_from_path=boot.img',
  'info',
  'repack --dest=image_package_repo_base',
  [['flash --current --serial my_serial1 --skip-vbmeta=True ',
    'adb -s my_serial1 root',
    'dut --operation=wifi_on --serial=my_serial1 --ap=GoogleGuest',
    'dut --operation=volume_mute --serial=my_serial1 --version=9.0'],
   ['flash --current --serial my_serial2 --skip-vbmeta=True ',
    'adb -s my_serial2 root',
    'dut --operation=wifi_on --serial=my_serial2 --ap=GoogleGuest',
    'dut --operation=volume_mute --serial=my_serial2 --version=9.0'],
   ['flash --current --serial my_serial3 --skip-vbmeta=True ',
    'adb -s my_serial3 root',
    'dut --operation=wifi_on --serial=my_serial3 --ap=GoogleGuest',
    'dut --operation=volume_mute --serial=my_serial3 --version=9.0']],
  'test --suite vts --keep-result -- vts --shards 3  --serial my_serial1 --serial my_serial2 --serial my_serial3',
  'retry --suite vts --count 3  --shards 3 --serial my_serial1 --serial my_serial2 --serial my_serial3',
  'sheet --src {result_zip} --dest report_spreadsheet_id --extra_rows logs,report_bucket/{suite_plan}/vts/{branch}/{target}/my_build_target_{build_id}_{timestamp}/',
  'upload --src={result_full} --dest=report_bucket/{suite_plan}/vts/{branch}/{target}/my_build_target_{build_id}_{timestamp}/ --report_path=report_bucket/suite_result/{timestamp_year}/{timestamp_month}/{timestamp_day} --clear_results=True']

