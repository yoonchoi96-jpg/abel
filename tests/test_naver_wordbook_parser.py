"""Offline unit tests: synthetic data only, never real Naver account content."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from naver_wordbook_parser import (
    NaverSchemaError, normalize_card, classify_cards,
    validate_folder_pages, build_snapshot,
)


def fake_card(word, folder, number, *, meaning="절제하다", pinyin=None):
    prons = [{"pinyin": pinyin}] if pinyin else [{"unknown_pron_key": "unknown"}]
    entry = {
        "members": [{"entry_name": word, "prons": prons}],
        "means": [{
            "show_mean": meaning, "part_name": "동사", "language": "ko",
            "examples": [{"example": "synthetic"}],
        }],
        "mix_pron": "unverified_mix_pron",
    }
    return {
        "id": "c" + str(number) + folder,
        "entryId": "e" + str(number),
        "wordbookId": folder, "name": word,
        "content": json.dumps({"entry": entry}, ensure_ascii=False),
        "read": False, "createDate": 123,
    }


class ParserTests(unittest.TestCase):
    def test_decodes_embedded_entry_and_means(self):
        parsed = normalize_card(fake_card("维持", "book1", 1, meaning="<b>유지하다</b>"))
        self.assertEqual(parsed["word"], "维持")
        self.assertEqual(parsed["definitions"][0]["meaning"], "유지하다")
        self.assertEqual(parsed["definitions"][0]["part_of_speech"], "동사")
        self.assertEqual(parsed["mix_pron_unverified"], "unverified_mix_pron")
        self.assertTrue(parsed["missing_pinyin"])

    def test_explicit_pinyin_only(self):
        parsed = normalize_card(fake_card("趋势", "book2", 1, pinyin="qūshì"))
        self.assertEqual(parsed["pinyin"], "qūshì")
        self.assertFalse(parsed["missing_pinyin"])

    def test_duplicate_folder_counts_once(self):
        cards = [
            fake_card("维护", "A", 1),
            fake_card("维护", "A", 2),
            fake_card("维护", "B", 3),
            fake_card("忽略", "C", 4),
        ]
        classified = {x["word"]: x for x in classify_cards(cards)}
        self.assertEqual(classified["维护"]["folder_count"], 2)
        self.assertEqual(classified["维护"]["priority"], "P3")
        self.assertEqual(classified["忽略"]["priority"], "P4")

    def test_priority_four_or_more_folders(self):
        cards = [fake_card("适应", f"book{i}", i) for i in range(5)]
        result = classify_cards(cards)[0]
        self.assertEqual(result["priority"], "P1")
        self.assertEqual(result["folder_count"], 5)

    def test_missing_content_fails_closed(self):
        card = fake_card("维护", "A", 1)
        card["content"] = "not json"
        with self.assertRaises(NaverSchemaError):
            normalize_card(card)

    def test_one_based_complete_page(self):
        cards = [fake_card("潜力", "folderA", 1), fake_card("损失", "folderA", 2)]
        response = {"data": {"m_total": 2, "m_total_pages": 1,
                              "m_current_page": 1, "m_items": cards}}
        self.assertEqual(len(validate_folder_pages("folderA", [response], 2)), 2)

    def test_missing_pages_not_counted_as_deletions(self):
        response = {"data": {"m_total": 2, "m_total_pages": 2,
                             "m_current_page": 1,
                             "m_items": [fake_card("潜力", "folderA", 1)]}}
        with self.assertRaises(NaverSchemaError):
            validate_folder_pages("folderA", [response], 2)

    def test_repeated_card_id_rejected(self):
        card = fake_card("潜力", "folderA", 1)
        response = {"data": {"m_total": 2, "m_total_pages": 1,
                             "m_current_page": 1, "m_items": [card, card]}}
        with self.assertRaises(NaverSchemaError):
            validate_folder_pages("folderA", [response], 2)

    def test_folder_mismatch_rejected(self):
        response = {"data": {"m_total": 1, "m_total_pages": 1,
                             "m_current_page": 1,
                             "m_items": [fake_card("潜力", "other", 1)]}}
        with self.assertRaises(NaverSchemaError):
            validate_folder_pages("folderA", [response], 1)

    def test_contiguous_pages_required_even_when_counts_match(self):
        cards1 = [fake_card("维护", "A", 1)]
        cards3 = [fake_card("潜力", "A", 2)]
        pages = [
            {"data": {"m_total": 2, "m_total_pages": 2,
                      "m_current_page": 1, "m_items": cards1}},
            {"data": {"m_total": 2, "m_total_pages": 2,
                      "m_current_page": 3, "m_items": cards3}},
        ]
        with self.assertRaises(NaverSchemaError):
            validate_folder_pages("A", pages, 2)

    def test_folder_count_must_match_authoritative_total(self):
        folders = [{"id": "A", "name": "A", "wordCount": 1}]
        response = {"data": {"m_total": 1, "m_total_pages": 1,
                             "m_current_page": 1,
                             "m_items": [fake_card("适应", "A", 1)]}}
        with self.assertRaises(NaverSchemaError):
            build_snapshot(folders, {"A": [response]}, reported_folder_count=2)

    def test_complete_preview_with_multiple_folders(self):
        folders = [
            {"id": "A", "name": "A", "wordCount": 1},
            {"id": "B", "name": "B", "wordCount": 1},
        ]
        pages = {
            folder: [{"data": {
                "m_total": 1, "m_total_pages": 1, "m_current_page": 1,
                "m_items": [fake_card("损失", folder, i)],
            }}] for i, folder in enumerate(("A", "B"), 1)
        }
        snapshot = build_snapshot(folders, pages, reported_folder_count=2)
        self.assertEqual(snapshot["saved_card_count"], 2)
        self.assertEqual(snapshot["words"][0]["folder_count"], 2)
        self.assertEqual(snapshot["words"][0]["priority"], "P3")

    def test_build_snapshot_needs_every_folder(self):
        folders = [{"id": "folderA", "name": "A", "wordCount": 1},
                   {"id": "folderB", "name": "B", "wordCount": 1}]
        page = {"data": {"m_total": 1, "m_total_pages": 1,
                         "m_current_page": 1,
                         "m_items": [fake_card("潜力", "folderA", 1)]}}
        with self.assertRaises(NaverSchemaError):
            build_snapshot(folders, {"folderA": [page]}, reported_folder_count=2)


if __name__ == "__main__":
    unittest.main()
