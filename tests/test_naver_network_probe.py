"""Network-free tests for the owner-controlled Naver request metadata probe."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from naver_network_probe import (  # noqa: E402
    MetadataCollector, has_word_cards, sanitized_endpoint, skeleton,
    embedded_content_structure, content_schema_for_word_cards,
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

    def test_array_record_schema_is_visible_without_values(self):
        private = {
            "data": {
                "m_items": [{
                    "entryName": "PRIVATE_CHINESE_WORD",
                    "pinyin": "PRIVATE_PINYIN",
                    "meaning": "PRIVATE_KOREAN_MEANING",
                }]
            }
        }
        shape = skeleton(private)
        fields = shape["fields"]["data"]["fields"]["m_items"]["item"]["fields"]
        self.assertEqual(fields["entryName"], {"type": "string"})
        self.assertEqual(fields["pinyin"], {"type": "string"})
        for secret in ("PRIVATE_CHINESE_WORD", "PRIVATE_PINYIN", "PRIVATE_KOREAN_MEANING"):
            self.assertNotIn(secret, json.dumps(shape))

    def test_embedded_json_redacts_all_values(self):
        value = json.dumps({"pinyin": "pRIVATE", "definitions": [{"ko": "기밀단어"}]})
        metadata = embedded_content_structure(value)
        self.assertEqual(metadata["format"], "json_string")
        fields = metadata["schema"]["fields"]
        self.assertEqual(fields["pinyin"], {"type": "string"})
        self.assertNotIn("pRIVATE", json.dumps(metadata, ensure_ascii=False))
        self.assertNotIn("기밀단어", json.dumps(metadata, ensure_ascii=False))

    def test_embedded_html_redacts_text_and_attributes(self):
        value = '<p class="secret">私人단어 <span data-id="secret123">meaning</span></p>'
        metadata = embedded_content_structure(value)
        self.assertEqual(metadata["format"], "html_fragment")
        self.assertEqual(metadata["tags"], ["p", "span"])
        for secret in ("secret", "secret123", "私人", "meaning"):
            self.assertNotIn(secret, json.dumps(metadata, ensure_ascii=False))

    def test_embedded_plaintext_language_flags_not_text(self):
        metadata = embedded_content_structure("私人 단어")
        self.assertEqual(metadata["format"], "plain_text")
        self.assertTrue(metadata["contains_hanzi"])
        self.assertTrue(metadata["contains_hangul"])
        self.assertNotIn("私人", json.dumps(metadata, ensure_ascii=False))

    def test_card_content_shape_missing_items(self):
        self.assertIsNone(content_schema_for_word_cards({"data": {"m_items": []}}))

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

    def test_folder_list_is_not_word_card_response(self):
        collector = MetadataCollector()
        folder = "https://learn.dict.naver.com/gateway-api/zhkodict/mywordbook/wordbook/list.dict"
        cards = "https://learn.dict.naver.com/gateway-api/zhkodict/mywordbook/word/list/search"
        collector.record(url=folder, method="GET", status=200,
                         content_type="application/json", body=b'{"data":{"m_items":[]}}')
        self.assertFalse(has_word_cards(collector))
        collector.record(url=cards, method="GET", status=200,
                         content_type="application/json", body=b'{"data":{"m_items":[]}}')
        self.assertTrue(has_word_cards(collector))

    def test_unrelated_path_without_relevant_json_not_captured(self):
        c = MetadataCollector()
        c.record(url="https://learn.dict.naver.com/telemetry/metrics",
                 method="POST", status=200, content_type="application/json",
                 body=b'{"status":"ok"}')
        self.assertFalse(c.report()["candidate_endpoints"])


if __name__ == "__main__":
    unittest.main()
