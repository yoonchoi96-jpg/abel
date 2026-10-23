"""No-network synthetic coverage for proposed seven-stage Abel priorities."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from naver_priority_p1_p7 import produce, rank_from_evidence, reference_level
from naver_wordbook_checkpoint import digest


def card(word, folder, n, malformed=False):
    return {
        "id": str(n) + folder,
        "wordbookId": folder,
        "name": word,
        "content": (
            '{"other": 2}' if malformed
            else json.dumps({"entry": {
                "members": [{"entry_name": word, "prons": []}],
                "means": [{"show_mean": "뜻", "part_name": "명사"}],
            }}, ensure_ascii=False)),
    }


def entry(name, folder, cards):
    pages = [{
        "data": {
            "m_total": len(cards), "m_current_page": 1,
            "m_total_pages": 1, "m_items": cards,
        },
        "meta": {"status": 1},
    }]
    return folder, {
        "metadata": {"id": folder, "name": name, "wordCount": len(cards)},
        "digest": digest(pages), "pages": pages,
    }


class PriorityP1P7Tests(unittest.TestCase):
    def test_levels_and_unknown_single_curated_folder(self):
        self.assertEqual(rank_from_evidence(1, {5})[0], "P4")
        self.assertEqual(rank_from_evidence(1, {6})[0], "P5")
        self.assertEqual(rank_from_evidence(1, {79})[0], "P6")
        self.assertEqual(rank_from_evidence(1, set())[0], "P7")
        self.assertEqual(rank_from_evidence(1, {5, 6, 79})[0], "P4")

    def test_distinct_curated_folders_override_exam_level(self):
        self.assertEqual(rank_from_evidence(4, {79})[0], "P1")
        self.assertEqual(rank_from_evidence(3, {5})[0], "P2")
        self.assertEqual(rank_from_evidence(2, set())[0], "P3")

    def test_reference_folders_do_not_count_as_user_curated_folders(self):
        cached = dict([
            entry("내가 찾은 단어", "A", [
                card("词语", "A", 1), card("生词", "A", 2),
                card("文学", "A", 3), card("新词", "A", 4),
                card("未知", "A", 5),
            ]),
            entry("신HSK_5급 필수단어 5탄", "R5", [
                card("词语", "R5", 6), card("生词", "R5", 7),
            ]),
            entry("신HSK_6급 필수단어 10탄", "R6", [
                card("生词", "R6", 8),
            ]),
        ])
        result = produce({"entries": cached}, {"文学"}, {"新词"})
        byword = {r["word"]: r for r in result["words"]}
        self.assertEqual(byword["词语"]["priority"], "P4")
        self.assertEqual(byword["生词"]["priority"], "P4")
        self.assertEqual(byword["文学"]["priority"], "P5")
        self.assertEqual(byword["新词"]["priority"], "P6")
        self.assertEqual(byword["未知"]["priority"], "P7")
        self.assertEqual(result["reference_folder_count"], 2)
        self.assertEqual(result["curated_folder_count"], 1)
        self.assertEqual(result["distinct_curated_words"], 5)
        self.assertEqual(result["priority_counts"]["P1"], 0)
        self.assertEqual(result["priority_counts"]["P4"], 2)
        self.assertEqual(result["reference_card_count"], 3)

    def test_reference_only_word_excluded_from_study(self):
        cached = dict([
            entry("내가 찾은 단어", "A", [card("学习", "A", 1)]),
            entry("신HSK_6급 필수단어 1탄", "REF", [card("高阶", "REF", 2)]),
        ])
        result = produce({"entries": cached}, {"学习"}, {"高阶"})
        self.assertEqual([item["word"] for item in result["words"]], ["学习"])
        self.assertEqual(result["priority_counts"]["P5"], 1)

    def test_unsupported_cards_keep_priorities_provisional(self):
        cached = dict([entry("내가 찾은 단어", "A",
                             [card("完好", "A", 1), card("异常", "A", 2, True)])])
        result = produce({"entries": cached}, set(), set())
        self.assertEqual(result["unresolved_card_count"], 1)
        self.assertFalse(result["complete"])
        self.assertTrue(result["priority_counts_provisional"])

    def test_exact_reference_label_required(self):
        self.assertEqual(reference_level("신HSK_5급 필수단어 10탄"), 5)
        self.assertEqual(reference_level("신HSK_6급 필수단어 1탄"), 6)
        self.assertIsNone(reference_level("내 HSK6 오답노트"))
        self.assertIsNone(reference_level("HSK 6급 개인암기"))
        self.assertIsNone(reference_level("중국어 5급 단어장"))


if __name__ == "__main__":
    unittest.main()
