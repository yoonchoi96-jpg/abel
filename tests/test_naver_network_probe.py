"""Network-free tests for the owner-controlled Naver request metadata probe."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from naver_network_probe import (  # noqa: E402
    MetadataCollector, sanitized_endpoint, skeleton,
)


class SafeMetadataTest(unittest.TestCase):
    def test_no_query_values_or_hash(self):
        url = ("https://learn.dict.naver.com/wordbook/zhkodict/api/list"
               "?wbId=secret-folder-123&csrf=sensitive-value#private")
        result = sanitized_endpoint(url)
        self.assertIsNotNone(result)
        dumped = json.dumps(result)
        self.assertIn("wbId", dumped)
        self.assertNotIn("secret-folder-123", dumped)
        self.assertNotIn("sensitive-value", dumped)
        self.assertNotIn("private", dumped)

    def test_sensitive_or_non_naver_hosts_excluded(self):
        self.assertIsNone(sanitized_endpoint(
            "https://nid.naver.com/nidlogin.login?token=secret"))
        self.assertIsNone(sanitized_endpoint(
            "https://malicious-naver.com/wordbook?token=secret"))
        self.assertIsNone(sanitized_endpoint(
            "https://api.naver.com/oauth/authorize?token=secret"))

    def test_response_shape_never_contains_values(self):
        private = {
            "wordbooks": [{
                "wbId": "USER_PERSONAL_FOLDER_ID",
                "name": "MY_SECRET_FOLDER",
                "words": [{"word": "PRIVATE_CHINESE_WORD", "meaning": "PRIVATE_MEANING"}],
            }],
            "apiKey": "SECRET_TOKEN",
        }
        shape = skeleton(private)
        raw = json.dumps(shape)
        for secret in (
            "USER_PERSONAL_FOLDER_ID", "MY_SECRET_FOLDER",
            "PRIVATE_CHINESE_WORD", "PRIVATE_MEANING", "SECRET_TOKEN",
        ):
            self.assertNotIn(secret, raw)
        self.assertEqual(shape["fields"]["wordbooks"]["type"], "array")

    def test_merges_repeated_endpoint_without_body(self):
        c = MetadataCollector()
        url = "https://learn.dict.naver.com/wordbook/api/folders?wbId=secret1"
        a = json.dumps({"wordbooks": [{"wbId": "id1", "name": "folder"}]}).encode()
        b = json.dumps({"wordbooks": [{"wbId": "id2", "name": "other"}]}).encode()
        c.record(url=url, method="GET", status=200,
                 content_type="application/json", body=a)
        c.record(url=url.replace("secret1", "secret2"), method="GET",
                 status=200, content_type="application/json", body=b)
        report = c.report()
        self.assertEqual(len(report["candidate_endpoints"]), 1)
        self.assertEqual(report["candidate_endpoints"][0]["observations"], 2)
        self.assertNotIn("secret1", json.dumps(report))
        self.assertNotIn("secret2", json.dumps(report))
        self.assertNotIn("id1", json.dumps(report))
        self.assertNotIn("other", json.dumps(report))

    def test_unrelated_path_without_relevant_json_not_captured(self):
        c = MetadataCollector()
        c.record(url="https://learn.dict.naver.com/telemetry/metrics",
                 method="POST", status=200, content_type="application/json",
                 body=b'{"status":"ok"}')
        self.assertFalse(c.report()["candidate_endpoints"])


if __name__ == "__main__":
    unittest.main()
