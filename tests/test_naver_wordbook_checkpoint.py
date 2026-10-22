"""Offline tests for resumable, private Naver wordbook checkpoints."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from naver_wordbook_checkpoint import (
    cached_pages, can_reuse_metadata, digest, load_cache, metadata, new_cache,
    remove_absent_folders, save_checkpoint,
)
from naver_wordbook_parser import NaverSchemaError


def folder(ident="A", *, changed=10, count=1):
    return {
        "id": ident,
        "name": "wordbook",
        "wordCount": count,
        "updateTimestamp": changed,
        "lastWordTimestamp": 8,
        "lastReciteTimestamp": 5,
        "lastLearnTimestamp": 6,
    }


def pages(ident="A", count=1):
    items = [{"id": "{}-{}".format(ident, i), "wordbookId": ident}
             for i in range(count)]
    return [{
        "data": {"m_total": count,
                 "m_total_pages": 1 if count else 0,
                 "m_current_page": 1 if count else 0,
                 "m_items": items},
        "meta": {"status": 1},
    }]


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


class CheckpointTests(unittest.TestCase):
    def test_first_run_is_uncached(self):
        self.assertIsNone(cached_pages(new_cache(), folder()))

    def test_complete_folder_can_be_reused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            state = new_cache()
            save_checkpoint(state, folder(), pages(), path, write)
            fresh = load_cache(path)
            self.assertEqual(cached_pages(fresh, folder()), pages())

    def test_change_timestamp_forces_refetch(self):
        state = new_cache()
        state["entries"]["A"] = {
            "metadata": metadata(folder(changed=10)),
            "pages": pages(),
            "digest": digest(pages()),
        }
        self.assertIsNone(cached_pages(state, folder(changed=11)))
        self.assertIsNone(cached_pages(state, folder(count=2)))

    def test_missing_marker_disables_skip(self):
        candidate = folder()
        candidate["lastLearnTimestamp"] = None
        self.assertFalse(can_reuse_metadata(metadata(candidate)))
        self.assertIsNone(cached_pages(new_cache(), candidate))

    def test_cache_corruption_rejected(self):
        state = new_cache()
        state["entries"]["A"] = {
            "metadata": metadata(folder()),
            "pages": pages(),
            "digest": "corrupt",
        }
        with self.assertRaises(NaverSchemaError):
            cached_pages(state, folder())

    def test_invalid_cached_folder_data_rejected_even_with_digest(self):
        state = new_cache()
        bad_pages = pages(ident="WRONG")
        state["entries"]["A"] = {
            "metadata": metadata(folder()),
            "pages": bad_pages,
            "digest": digest(bad_pages),
        }
        with self.assertRaises(NaverSchemaError):
            cached_pages(state, folder())

    def test_missing_pages_never_cached(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            with self.assertRaises(NaverSchemaError):
                save_checkpoint(
                    new_cache(), folder(count=2), pages(count=1), path, write)
            self.assertFalse(path.exists())

    def test_resume_saved_folders_after_interruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            state = new_cache()
            save_checkpoint(state, folder("A"), pages("A"), path, write)
            state_after_interruption = load_cache(path)
            self.assertIsNotNone(cached_pages(
                state_after_interruption, folder("A")))
            self.assertIsNone(cached_pages(
                state_after_interruption, folder("B")))

    def test_deleted_folders_only_pruned_on_explicit_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            state = new_cache()
            save_checkpoint(state, folder("A"), pages("A"), path, write)
            save_checkpoint(state, folder("B"), pages("B"), path, write)
            remove_absent_folders(state, ["B"], path, write)
            after = load_cache(path)
            self.assertNotIn("A", after["entries"])
            self.assertIn("B", after["entries"])


if __name__ == "__main__":
    unittest.main()
