"""No-network tests for UI-driven Naver wordbook collection safety checks."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import naver_wordbook_collect as collector
from unittest.mock import patch
from naver_wordbook_collect import (
    atomic_save_if_changed, cards_url, fingerprint, require_page,
    safe_response_json,
)
from naver_wordbook_parser import NaverSchemaError


class DummyResponse:
    def __init__(self, data, *, status=200, content_type="application/json"):
        self.status = status
        self.headers = {"content-type": content_type}
        self._body = json.dumps(data, ensure_ascii=False).encode("utf-8")

    def body(self):
        return self._body


class CollectorTests(unittest.TestCase):
    def test_card_route_escapes_folder_and_preserves_page(self):
        route = cards_url({"id": "abc123", "name": "대만 旅行"}, 2)
        self.assertIn("wbId=abc123", route)
        self.assertIn("page=2", route)
        self.assertIn("%E6%97%85%E8%A1%8C", route)

    def test_complete_folder_metadata(self):
        payload = {"data": {"m_total": 19, "m_page": 1,
                            "m_totalPage": 1, "m_items": [{"id": "abc"}]}}
        items, total, page, count = require_page(payload, collection="folders")
        self.assertEqual((total, page, count), (19, 1, 1))
        self.assertEqual(items, [{"id": "abc"}])

    def test_card_page_mismatch_fails_closed(self):
        payload = {"data": {"m_total": 30, "m_current_page": 1,
                            "m_total_pages": 2, "m_items": []}}
        with self.assertRaises(NaverSchemaError):
            require_page(payload, collection="cards", expected_page=2)

    def test_empty_zero_based_page_is_allowed(self):
        payload = {"data": {"m_total": 0, "m_current_page": 0,
                            "m_total_pages": 0, "m_items": []}}
        self.assertEqual(require_page(
            payload, collection="cards", expected_page=1)[1], 0)

    def test_empty_nonzero_total_does_not_allow_index_zero(self):
        payload = {"data": {"m_total": 10, "m_current_page": 0,
                            "m_total_pages": 1, "m_items": []}}
        with self.assertRaises(NaverSchemaError):
            require_page(payload, collection="cards", expected_page=1)

    def test_status_one_with_valid_folder_page_is_accepted(self):
        response = DummyResponse({
            "meta": {"status": 1, "message": "Do not print actual message"},
            "data": {
                "m_total": 2, "m_page": 1, "m_totalPage": 1,
                "m_items": [{"id": "folderA"}, {"id": "folderB"}],
            },
        })
        payload = safe_response_json(response)
        items, total, number, pages = require_page(
            payload, collection="folders", expected_page=1)
        self.assertEqual((len(items), total, number, pages), (2, 2, 1, 1))

    def test_status_one_with_valid_card_page_is_accepted(self):
        response = DummyResponse({
            "meta": {"status": 1},
            "data": {
                "m_total": 1, "m_current_page": 1, "m_total_pages": 1,
                "m_items": [{"id": "card1", "wordbookId": "folderA"}],
            },
        })
        payload = safe_response_json(response)
        self.assertEqual(require_page(
            payload, collection="cards", expected_page=1)[1], 1)

    def test_status_one_with_error_body_is_still_rejected(self):
        response = DummyResponse({
            "meta": {"status": 1, "message": "temporary failure"},
            "data": {"error": "No user wordbook data"},
        })
        with self.assertRaises(NaverSchemaError):
            safe_response_json(response)

    def test_status_one_with_invalid_pagination_is_rejected(self):
        for invalid in (
            {"m_items": [], "m_total": "2", "m_page": 1, "m_totalPage": 1},
            {"m_items": [], "m_total": 2, "m_page": 1, "m_totalPage": "1"},
            {"m_items": "private", "m_total": 2, "m_page": 1, "m_totalPage": 1},
        ):
            with self.subTest(data=invalid):
                with self.assertRaises(NaverSchemaError):
                    safe_response_json(DummyResponse({
                        "meta": {"status": 1}, "data": invalid}))

    def test_other_application_code_not_allowed_even_with_valid_page(self):
        response = DummyResponse({
            "meta": {"status": 2},
            "data": {
                "m_total": 1, "m_page": 1, "m_totalPage": 1,
                "m_items": [{"id": "folderA"}],
            },
        })
        with self.assertRaises(NaverSchemaError):
            safe_response_json(response)

    def test_boolean_status_not_mistaken_for_one(self):
        response = DummyResponse({
            "meta": {"status": True},
            "data": {
                "m_total": 1, "m_page": 1, "m_totalPage": 1,
                "m_items": [{"id": "folderA"}],
            },
        })
        with self.assertRaises(NaverSchemaError):
            safe_response_json(response)

    def test_rejects_application_error_despite_http_200(self):
        with self.assertRaises(NaverSchemaError):
            safe_response_json(DummyResponse({
                "meta": {"status": 403, "message": "fail"}, "data": {}}))

    def test_unknown_application_code_is_reported_without_message(self):
        response = DummyResponse({
            "meta": {"status": 2000, "message": "PRIVATE_ACCOUNT_DATA"},
            "data": {"m_items": [{"id": "PRIVATE_FOLDER"}]},
        })
        with self.assertRaises(NaverSchemaError) as error:
            safe_response_json(response)
        self.assertIn("2000", str(error.exception))
        self.assertNotIn("PRIVATE_ACCOUNT_DATA", str(error.exception))
        self.assertNotIn("PRIVATE_FOLDER", str(error.exception))

    def test_unknown_application_status_string_is_not_exposed(self):
        response = DummyResponse({
            "meta": {"status": "SECRET_USER_TOKEN", "message": "PRIVATE"},
            "data": {},
        })
        with self.assertRaises(NaverSchemaError) as error:
            safe_response_json(response)
        self.assertIn("nonstandard_type_str", str(error.exception))
        self.assertNotIn("SECRET", str(error.exception))
        self.assertNotIn("PRIVATE", str(error.exception))

    def test_rejects_403_http(self):
        with self.assertRaises(NaverSchemaError):
            safe_response_json(DummyResponse({
                "meta": {"status": 0}, "data": {}}, status=403))

    def test_json_safety_cap(self):
        response = DummyResponse({"meta": {"status": 200}, "data": {"x": "a"}})
        response.headers["content-length"] = "9000000"
        with self.assertRaises(NaverSchemaError):
            safe_response_json(response)

    def test_fingerprint_independent_of_key_order(self):
        self.assertEqual(
            fingerprint({"word": "维持", "n": 2}),
            fingerprint({"n": 2, "word": "维持"}))

    def test_incomplete_run_writes_anonymized_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            def fail(_args, progress):
                progress("READING_FOLDER_CARDS", folder_count=19,
                         folder_index=3, completed_folders=2)
                raise NaverSchemaError("Word counts changed or disagree across pages")

            with patch.object(collector, "run", side_effect=fail), patch.object(
                sys, "argv", ["collect", "--output-dir", tmp]
            ):
                with self.assertRaises(SystemExit):
                    collector.main()
            path = Path(tmp) / "naver_wordbook_attempt.json"
            self.assertTrue(path.is_file())
            attempt = json.loads(path.read_text())
            self.assertEqual(attempt["stage"], "INCOMPLETE")
            self.assertEqual(attempt["error_stage"], "READING_FOLDER_CARDS")
            self.assertEqual(attempt["completed_folders"], 2)
            self.assertEqual(attempt["folder_count"], 19)
            self.assertFalse((Path(tmp) / "naver_wordbook_verified.json").exists())

    def test_snapshot_file_writes_only_when_changed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "snapshot.json"
            self.assertTrue(atomic_save_if_changed(path, {"words": ["维持"]}))
            self.assertFalse(atomic_save_if_changed(path, {"words": ["维持"]}))
            self.assertTrue(atomic_save_if_changed(path, {"words": ["维护"]}))
            self.assertEqual(json.loads(path.read_text())["words"], ["维护"])


if __name__ == "__main__":
    unittest.main()
