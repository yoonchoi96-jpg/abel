#!/usr/bin/env python3
"""Owner-local checkpoint/reuse for Abel's read-only Naver UI collector.

Contains PRIVATE wordbook data. Store only on the Mac, never in GitHub or
Google Drive. Refuse reuse if source metadata or integrity checks differ.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from naver_wordbook_parser import NaverSchemaError, validate_folder_pages

SCHEMA = "abel.naver.local_checkpoint.v1"
FRESHNESS_FIELDS = (
    "id", "name", "wordCount", "updateTimestamp", "lastWordTimestamp",
    "lastReciteTimestamp", "lastLearnTimestamp",
)
CHANGE_MARKERS = (
    "updateTimestamp", "lastWordTimestamp",
    "lastReciteTimestamp", "lastLearnTimestamp",
)


def digest(value):
    content = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def metadata(folder):
    if not isinstance(folder, dict):
        raise NaverSchemaError("invalid folder metadata")
    return {k: folder.get(k) for k in FRESHNESS_FIELDS}


def can_reuse_metadata(meta):
    """No marker => no skipping; never assume an untracked folder is unchanged."""
    if not isinstance(meta, dict) or not meta.get("id") or not meta.get("name"):
        return False
    if type(meta.get("wordCount")) is not int:
        return False
    # All markers must be present. Lack of a marker is not a valid no-change proof.
    return all(type(meta.get(name)) is int for name in CHANGE_MARKERS)


def new_cache():
    return {"schema": SCHEMA, "entries": {}}


def load_cache(path):
    path = Path(path).expanduser()
    if not path.exists():
        return new_cache()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise NaverSchemaError(
            "Local checkpoint file is corrupt; refuse reuse") from exc
    if (not isinstance(raw, dict) or raw.get("schema") != SCHEMA
            or not isinstance(raw.get("entries"), dict)):
        raise NaverSchemaError("Invalid checkpoint format; refuse reuse")
    return raw


def cached_pages(cache, folder):
    """Return validated pages if and only if all change markers are stable."""
    meta = metadata(folder)
    if not can_reuse_metadata(meta):
        return None
    entry = cache["entries"].get(meta["id"])
    if not isinstance(entry, dict) or entry.get("metadata") != meta:
        return None
    pages = entry.get("pages")
    if not isinstance(pages, list) or entry.get("digest") != digest(pages):
        raise NaverSchemaError("Cached wordbook pages failed integrity check")
    # No partial or off-folder cards can be reused.
    validate_folder_pages(meta["id"], pages, meta["wordCount"])
    return pages


def save_checkpoint(cache, folder, pages, destination, atomic_save):
    """Persist a completed folder immediately so interrupted runs can resume."""
    meta = metadata(folder)
    validate_folder_pages(meta["id"], pages, meta["wordCount"])
    cache["entries"][meta["id"]] = {
        "metadata": meta, "digest": digest(pages), "pages": pages,
    }
    atomic_save(destination, cache)


def remove_absent_folders(cache, folder_ids, destination, atomic_save):
    """Prune only after all currently visible wordbooks have been verified."""
    valid = set(folder_ids)
    if not valid:
        raise NaverSchemaError("Refusing to prune against an empty folder index")
    if any(not isinstance(folder_id, str) for folder_id in valid):
        raise NaverSchemaError("Invalid ID in checkpoint prune")
    pruned = {
        folder_id: value for folder_id, value in cache["entries"].items()
        if folder_id in valid
    }
    if len(pruned) != len(cache["entries"]):
        cache["entries"] = pruned
        atomic_save(destination, cache)
