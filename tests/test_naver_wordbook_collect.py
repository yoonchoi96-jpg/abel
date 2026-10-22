"""No-network tests for UI-driven Naver wordbook collection safety checks."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
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

    def test_rejects_application_error_despite_http_200(self):
        with self.assertRaises(NaverSchemaError):
            safe_response_json(DummyResponse({
                "meta": {"status": 403, "message": "fail"}, "data": {}}))

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

    def test_snapshot_file_writes_only_when_changed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "snapshot.json"
            self.assertTrue(atomic_save_if_changed(path, {"words": ["维持"]}))
            self.assertFalse(atomic_save_if_changed(path, {"words": ["维持"]}))
            self.assertTrue(atomic_save_if_changed(path, {"words": ["维护"]}))
            self.assertEqual(json.loads(path.read_text())["words"], ["维护"])


if __name__ == "__main__":
    unittest.main()
