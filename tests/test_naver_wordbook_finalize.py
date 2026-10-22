"""Offline recovery tests: never require a Naver login or network."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from naver_wordbook_finalize import (
    finalize, snapshot_from_local_checkpoint, select_checkpoint_folders,
)
from naver_wordbook_checkpoint import new_cache, save_checkpoint
from naver_wordbook_parser import NaverSchemaError


def fake_card(number, folder, *, malformed=False):
    entry = {"entry": {
        "members": [{"entry_name": "维护", "prons": []}],
        "means": [{"show_mean": "유지하다", "part_name": "동사"}],
    }}
    return {
        "id": "{}-{}".format(folder, number), "wordbookId": folder,
        "name": "维护",
        "content": '{"unexpected": 1}' if malformed
                   else json.dumps(entry, ensure_ascii=False),
    }


def add_folder(cache, folder, cards, path):
    metadata = {
        "id": folder, "name": "local", "wordCount": len(cards),
        "updateTimestamp": 1, "lastWordTimestamp": 1,
        "lastReciteTimestamp": 1, "lastLearnTimestamp": 1,
    }
    pages = [{
        "data": {"m_total": len(cards), "m_total_pages": 1,
                 "m_current_page": 1, "m_items": cards},
        "meta": {"status": 1},
    }]
    def write(destination, payload):
        Path(destination).write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    save_checkpoint(cache, metadata, pages, path, write)


def attempt_file(path, *, completed=2, total=2, stage="INCOMPLETE"):
    report = {
        "format": "abel.naver.collect_attempt.v1",
        "stage": stage, "error_stage": "VERIFYING_ALL_PAGES",
        "completed_folders": completed, "folder_count": total,
        "started_at": "2026-10-22T19:31:11Z",
    }
    path.write_text(json.dumps(report), encoding="utf-8")


class OfflineFinalizeTests(unittest.TestCase):
    def test_reconstructs_completed_19_folders_without_browser(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = new_cache()
            path = root / "checkpoint.json"
            for n in range(19):
                folder = "F{:02d}".format(n)
                add_folder(state, folder, [
                    fake_card(n, folder, malformed=(n == 7)),
                ], path)
            attempt_file(root / "naver_wordbook_attempt.json",
                         completed=19, total=19)
            stats = finalize(checkpoint_path=path, output_dir=root)
            self.assertEqual(stats["folder_count"], 19)
            self.assertEqual(stats["saved_card_count"], 19)
            self.assertEqual(stats["unresolved_card_count"], 1)
            self.assertTrue(stats["collection_complete"])
            self.assertFalse(stats["classification_complete"])
            self.assertFalse(stats["complete"])
            self.assertEqual(stats["distinct_words"], 1)
            self.assertTrue((root / "naver_wordbook_verified.json").is_file())
            snap = json.loads(
                (root / "naver_wordbook_verified.json").read_text())
            self.assertTrue(snap["verified_card_pages"])
            self.assertEqual(snap["unresolved_cards"][0]["reason"],
                             "unsupported_content_structure")
            # Full private raw data is preserved in the local checkpoint.
            self.assertEqual(
                json.loads(path.read_text())["entries"]["F07"]["pages"][0]
                ["data"]["m_items"][0]["content"], '{"unexpected": 1}')

    def test_stale_extra_folder_requires_and_accepts_exact_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "checkpoint.json"
            state = new_cache()
            add_folder(state, "A", [fake_card(1, "A")], path)
            add_folder(state, "B", [fake_card(2, "B")], path)
            add_folder(state, "STALE", [fake_card(3, "STALE")], path)
            attempt_file(root / "naver_wordbook_attempt.json",
                         completed=2, total=2)

            with self.assertRaisesRegex(NaverSchemaError, "Checkpoint has 3"):
                finalize(checkpoint_path=path, output_dir=root)

            live = [state["entries"][ident]["metadata"] for ident in ("A", "B")]
            stats = finalize(checkpoint_path=path, output_dir=root,
                             current_folders=live)
            self.assertEqual(stats["folder_count"], 2)
            self.assertEqual(stats["saved_card_count"], 2)
            self.assertEqual(stats["unresolved_card_count"], 0)
            self.assertIn("STALE", state["entries"])
            self.assertEqual(len(state["entries"]), 3)

    def test_index_reconciliation_rejects_wrong_or_changed_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "checkpoint.json"
            state = new_cache()
            add_folder(state, "A", [fake_card(1, "A")], path)
            add_folder(state, "B", [fake_card(2, "B")], path)
            matching = [state["entries"]["A"]["metadata"],
                        state["entries"]["B"]["metadata"]]
            with self.assertRaises(NaverSchemaError):
                select_checkpoint_folders(state["entries"], 2, [
                    matching[0], {"id": "UNKNOWN", "name": "other"}])
            changed = dict(matching[0], wordCount=2)
            with self.assertRaisesRegex(NaverSchemaError, "changed"):
                select_checkpoint_folders(state["entries"], 2,
                                          [changed, matching[1]])
            with self.assertRaisesRegex(NaverSchemaError, "Duplicate"):
                select_checkpoint_folders(state["entries"], 2,
                                          [matching[0], matching[0]])
            self.assertEqual(len(select_checkpoint_folders(
                state["entries"], 2, matching)), 2)

    def test_reconciled_index_requires_all_nineteen_actual_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "checkpoint.json"
            state = new_cache()
            for n in range(19):
                add_folder(state, "F{:02d}".format(n),
                           [fake_card(n, "F{:02d}".format(n))], path)
            add_folder(state, "OLD", [fake_card(99, "OLD")], path)
            attempt_file(root / "naver_wordbook_attempt.json",
                         completed=19, total=19)
            matching = [state["entries"]["F{:02d}".format(n)]["metadata"]
                        for n in range(19)]
            result = finalize(checkpoint_path=path, output_dir=root,
                              current_folders=matching)
            self.assertEqual(result["folder_count"], 19)
            self.assertEqual(result["saved_card_count"], 19)
            self.assertTrue(result["classification_complete"])

    def test_refuses_missing_checkpoint_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "checkpoint.json"
            state = new_cache()
            add_folder(state, "F00", [fake_card(0, "F00")], path)
            attempt_file(root / "naver_wordbook_attempt.json", completed=2, total=2)
            with self.assertRaises(NaverSchemaError):
                finalize(checkpoint_path=path, output_dir=root)
            self.assertFalse((root / "naver_wordbook_verified.json").exists())

    def test_refuses_early_collection_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "checkpoint.json"
            state = new_cache()
            add_folder(state, "F00", [fake_card(0, "F00")], path)
            attempt_file(root / "naver_wordbook_attempt.json",
                         completed=0, total=1)
            with self.assertRaises(NaverSchemaError):
                snapshot_from_local_checkpoint(
                    path, root / "naver_wordbook_attempt.json")
            self.assertFalse((root / "naver_wordbook_verified.json").exists())

    def test_repeat_finalize_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "checkpoint.json"
            state = new_cache()
            add_folder(state, "F00", [fake_card(0, "F00")], path)
            attempt_file(root / "naver_wordbook_attempt.json", completed=1, total=1)
            first = finalize(checkpoint_path=path, output_dir=root)
            second = finalize(checkpoint_path=path, output_dir=root)
            self.assertEqual(first["sha256"], second["sha256"])
            self.assertEqual(first["verified_at"], second["verified_at"])


if __name__ == "__main__":
    unittest.main()
