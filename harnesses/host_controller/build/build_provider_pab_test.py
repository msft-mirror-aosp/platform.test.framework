#!/usr/bin/env python
#
# Copyright (C) 2017 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import unittest
from host_controller.build import build_provider_pab

try:
    from unittest import mock
except ImportError:
    import mock

from requests.models import Response


class BuildProviderPABTest(unittest.TestCase):
    """Tests for Partner Android Build client."""

    def setUp(self):
        self.client = build_provider_pab.BuildProviderPAB()
        self.client.XSRF_STORE = None

    def tearDown(self):
        del self.client

    @mock.patch("build_provider_pab.flow_from_clientsecrets")
    @mock.patch("build_provider_pab.run_flow")
    @mock.patch("build_provider_pab.Storage.get")
    @mock.patch('build_provider_pab.BuildProviderPAB._credentials')
    def testAuthenticationNew(self, mock_creds, mock_storage_get, mock_rf,
                              mock_ffc):
        mock_creds.invalid = True
        build_provider_pab.flow_from_clientsecrets = mock_ffc
        build_provider_pab.run_flow = mock_rf
        self.client.Authenticate()
        mock_ffc.assert_called_once()
        mock_storage_get.assert_called_once()
        mock_rf.assert_called_once()

    @mock.patch("build_provider_pab.flow_from_clientsecrets")
    @mock.patch("build_provider_pab.run_flow")
    @mock.patch("build_provider_pab.Storage.get")
    @mock.patch('build_provider_pab.BuildProviderPAB._credentials')
    def testAuthenticationStale(self, mock_creds, mock_storage_get, mock_rf,
                                mock_ffc):
        mock_creds.invalid = False
        mock_creds.access_token_expired = True
        build_provider_pab.flow_from_clientsecrets = mock_ffc
        build_provider_pab.run_flow = mock_rf
        mock_storage_get.return_value = mock_creds
        self.client.Authenticate()
        mock_ffc.assert_called_once()
        mock_storage_get.assert_called_once()
        mock_rf.assert_not_called()
        mock_creds.refresh.assert_called_once()

    @mock.patch("build_provider_pab.flow_from_clientsecrets")
    @mock.patch("build_provider_pab.run_flow")
    @mock.patch("build_provider_pab.Storage.get")
    @mock.patch('build_provider_pab.BuildProviderPAB._credentials')
    def testAuthenticationFresh(self, mock_creds, mock_storage_get, mock_rf,
                                mock_ffc):
        mock_creds.invalid = False
        mock_creds.access_token_expired = False
        build_provider_pab.flow_from_clientsecrets = mock_ffc
        build_provider_pab.run_flow = mock_rf
        mock_storage_get.return_value = mock_creds
        self.client.Authenticate()
        mock_ffc.assert_called_once()
        mock_storage_get.assert_called_once()
        mock_rf.assert_not_called()
        mock_creds.refresh.assert_not_called()

    @mock.patch('build_provider_pab.BuildProviderPAB._credentials')
    @mock.patch('requests.get')
    @mock.patch('__builtin__.open')
    def testDownloadArtifact(self, mock_open, mock_get, mock_creds):
        self.client._credentials = mock_creds
        artifact_url = (
            "https://partnerdash.google.com/build/gmsdownload/"
            "f_companion/label/clockwork.companion_20170906_211311_RC00/"
            "ClockworkCompanionGoogleWithGmsRelease_signed.apk?a=100621237")
        self.client.DownloadArtifact(
            artifact_url, 'ClockworkCompanionGoogleWithGmsRelease_signed.apk')
        self.client._credentials.apply.assert_called_with({})
        mock_get.assert_called_with(
            artifact_url, headers={}, stream=True)
        mock_open.assert_called_with(
            'ClockworkCompanionGoogleWithGmsRelease_signed.apk', 'wb')

    @mock.patch('build_provider_pab.BuildProviderPAB._credentials')
    @mock.patch('requests.post')
    def testGetArtifactURL(self, mock_post, mock_creds):
        self.client._xsrf = 'disable'
        response = Response()
        response.status_code = 200
        response._content = b'{ "result" : {"1": "this_url"}}'
        mock_post.return_value = response
        self.client._credentials = mock_creds
        url = self.client.GetArtifactURL(
            100621237,
            "4331445",
            "darwin_mac",
            "android-ndk-43345-darwin-x86_64.tar.bz2",
            "aosp-master-ndk",
            0,
            method='POST')
        mock_post.assert_called_with(
            'https://partner.android.com/build/u/0/_gwt/_rpc/buildsvc',
            data=mock.ANY,
            headers={
                'Content-Type': 'application/json',
                'x-alkali-account': 100621237,
            })
        self.assertEqual(url, "this_url")

    @mock.patch('build_provider_pab.BuildProviderPAB._credentials')
    @mock.patch('requests.post')
    def testGetArtifactURLBackendError(self, mock_post, mock_creds):
        self.client._xsrf = 'disable'
        response = Response()
        response.status_code = 200
        response._content = b'not JSON'
        mock_post.return_value = response
        self.client._credentials = mock_creds
        with self.assertRaises(ValueError) as cm:
            self.client.GetArtifactURL(
                100621237,
                "4331445",
                "darwin_mac",
                "android-ndk-43345-darwin-x86_64.tar.bz2",
                "aosp-master-ndk",
                0,
                method='POST')
        expected = "Backend error -- check your account ID"
        self.assertEqual(str(cm.exception), expected)

    @mock.patch('build_provider_pab.BuildProviderPAB._credentials')
    @mock.patch('requests.post')
    def testGetArtifactURLMissingResultError(self, mock_post, mock_creds):
        self.client._xsrf = 'disable'
        response = Response()
        response.status_code = 200
        response._content = b'{"result": {}}'
        mock_post.return_value = response
        self.client._credentials = mock_creds
        with self.assertRaises(ValueError) as cm:
            self.client.GetArtifactURL(
                100621237,
                "4331445",
                "darwin_mac",
                "android-ndk-43345-darwin-x86_64.tar.bz2",
                "aosp-master-ndk",
                0,
                method='POST')
        expected = "Resource not found"
        self.assertIn(expected, str(cm.exception))

    @mock.patch('build_provider_pab.BuildProviderPAB._credentials')
    @mock.patch('requests.post')
    def testGetArtifactURLInvalidXSRFError(self, mock_post, mock_creds):
        self.client._xsrf = 'disable'
        response = Response()
        response.status_code = 200
        response._content = b'{"error": {"code": -32000, "message":"Invalid"}}'
        mock_post.return_value = response
        self.client._credentials = mock_creds
        with self.assertRaises(ValueError) as cm:
            self.client.GetArtifactURL(
                100621237,
                "4331445",
                "darwin_mac",
                "android-ndk-43345-darwin-x86_64.tar.bz2",
                "aosp-master-ndk",
                0,
                method='POST')
        self.assertIn('Bad XSRF token', str(cm.exception))

    @mock.patch('build_provider_pab.BuildProviderPAB._credentials')
    @mock.patch('requests.post')
    def testGetArtifactURLExpiredXSRFError(self, mock_post, mock_creds):
        self.client._xsrf = 'disable'
        response = Response()
        response.status_code = 200
        response._content = b'{"error": {"code": -32001, "message":"Expired"}}'
        mock_post.return_value = response
        self.client._credentials = mock_creds
        with self.assertRaises(ValueError) as cm:
            self.client.GetArtifactURL(
                100621237,
                "4331445",
                "darwin_mac",
                "android-ndk-43345-darwin-x86_64.tar.bz2",
                "aosp-master-ndk",
                0,
                method='POST')
        self.assertIn('Expired XSRF token', str(cm.exception))

    @mock.patch('build_provider_pab.BuildProviderPAB._credentials')
    @mock.patch('requests.post')
    def testGetArtifactURLUnknownError(self, mock_post, mock_creds):
        self.client._xsrf = 'disable'
        response = Response()
        response.status_code = 200
        response._content = b'{"some_other_json": "foo"}'
        mock_post.return_value = response
        self.client._credentials = mock_creds
        with self.assertRaises(ValueError) as cm:
            self.client.GetArtifactURL(
                100621237,
                "4331445",
                "darwin_mac",
                "android-ndk-43345-darwin-x86_64.tar.bz2",
                "aosp-master-ndk",
                0,
                method='POST')
        self.assertIn('Unknown response from server', str(cm.exception))

    @mock.patch('build_provider_pab.BuildProviderPAB._credentials')
    @mock.patch('requests.post')
    def testGetBuildListSuccess(self, mock_post, mock_creds):
        self.client._xsrf = 'disable'
        response = Response()
        response.status_code = 200
        response._content = b'{"result": {"1": "foo"}}'
        mock_post.return_value = response
        self.client._credentials = mock_creds
        result = self.client.GetBuildList(
            100621237,
            "git_oc-treble-dev",
            "aosp_arm64_ab-userdebug",
            method='POST')
        self.assertEqual(result, "foo")
        mock_post.assert_called_with(
            'https://partner.android.com/build/u/0/_gwt/_rpc/buildsvc',
            data=mock.ANY,
            headers={
                'Content-Type': 'application/json',
                'x-alkali-account': 100621237,
            })

    @mock.patch('build_provider_pab.BuildProviderPAB._credentials')
    @mock.patch('requests.post')
    def testGetBuildListError(self, mock_post, mock_creds):
        self.client._xsrf = 'disable'
        response = Response()
        response.status_code = 200
        response._content = b'{"result": {"3": "foo"}}'
        mock_post.return_value = response
        self.client._credentials = mock_creds
        with self.assertRaises(ValueError) as cm:
            self.client.GetBuildList(
                100621237,
                "git_oc-treble-dev",
                "aosp_arm64_ab-userdebug",
                method='POST')
        self.assertIn('Build list not found', str(cm.exception))

    @mock.patch('build_provider_pab.BuildProviderPAB._credentials')
    @mock.patch('build_provider_pab.BuildProviderPAB.GetBuildList')
    def testGetLatestBuildIdSuccess(self, mock_gbl, mock_creds):
        self.client._xsrf = 'disable'
        mock_gbl.return_value = [{'7': 5, '1': 'bad'}, {'7': 7, '1': 'good'}]
        self.client.GetBuildList = mock_gbl
        result = self.client.GetLatestBuildId(
            100621237,
            "git_oc-treble-dev",
            "aosp_arm64_ab-userdebug",
            method='POST')
        self.assertEqual(result, 'good')

    @mock.patch('build_provider_pab.BuildProviderPAB._credentials')
    @mock.patch('build_provider_pab.BuildProviderPAB.GetBuildList')
    def testGetLatestBuildIdEmpty(self, mock_gbl, mock_creds):
        self.client._xsrf = 'disable'
        mock_gbl.return_value = []
        self.client.GetBuildList = mock_gbl
        with self.assertRaises(ValueError) as cm:
            result = self.client.GetLatestBuildId(
                100621237,
                "git_oc-treble-dev",
                "aosp_arm64_ab-userdebug",
                method='POST')
        self.assertIn("No builds found for", str(cm.exception))

    @mock.patch('build_provider_pab.BuildProviderPAB._credentials')
    @mock.patch('build_provider_pab.BuildProviderPAB.GetBuildList')
    def testGetLatestBuildIdAllBad(self, mock_gbl, mock_creds):
        self.client._xsrf = 'disable'
        mock_gbl.return_value = [{'7': 0}, {'7': 0}]
        self.client.GetBuildList = mock_gbl
        with self.assertRaises(ValueError) as cm:
            result = self.client.GetLatestBuildId(
                100621237,
                "git_oc-treble-dev",
                "aosp_arm64_ab-userdebug",
                method='POST')
        self.assertEqual(
            "No complete builds found: 2 failed or incomplete builds found",
            str(cm.exception))


if __name__ == "__main__":
    unittest.main()
