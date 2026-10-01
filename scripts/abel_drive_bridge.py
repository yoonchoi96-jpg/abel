#!/usr/bin/env python3
"""Abel <-> Google Drive bridge.

No Gemini API and no Google API calls are made here.
Only a local Google Drive sync folder is used as the handoff layer.
"""
from pathlib import Path
import fcntl
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone

HOME = Path.home()
SRC = HOME / ".naver_wordbook/exports/abel_classified.json"
DST = HOME / ".naver_wordbook/exports/abel_gemini_education.json"
LOCK = HOME / ".naver_wordbook/.abel_drive_bridge.lock"
SCHEMA_VERSION = "abel.education.v1"


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def root():
    configured = os.environ.get("ABEL_DRIVE_DIR")
    if configured:
        return Path(configured).expanduser()
    cloud = HOME / "Library/CloudStorage"
    candidates = sorted(cloud.glob("GoogleDrive-*/My Drive")) if cloud.exists() else []
    if candidates:
        return candidates[0] / "Abel"
    raise SystemExit("Set ABEL_DRIVE_DIR to your local Google Drive/Abel folder")


def read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except (json.JSONDecodeError, OSError) as exc:
        raise SystemExit(f"Invalid JSON: {path}: {exc}")


def atomic_write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def completed_ids(done):
    return {
        str(item.get("word_id"))
        for item in done
        if isinstance(item, dict) and item.get("word_id") is not None
    }


def pending_ids(inbox):
    ids = set()
    for path in inbox.glob("batch-*.json"):
        batch = read_json(path, {})
        for word in batch.get("words", []):
            if isinstance(word, dict) and word.get("id") is not None:
                ids.add(str(word["id"]))
    return ids


def find_source_batch(inbox, archive, batch_id):
    filename = f"{batch_id}.json"
    candidates = [inbox / filename, archive / filename]
    for path in candidates:
        if path.exists():
            return path
    return None


def export_pending(inbox, data, done):
    completed = completed_ids(done)
    pending = pending_ids(inbox)
    words = [
        word for word in data.get("words", [])
        if isinstance(word, dict)
        and word.get("id") is not None
        and str(word["id"]) not in completed
        and str(word["id"]) not in pending
    ]
    if not words:
        return 0

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    batch_id = f"abel-{stamp}"
    payload = {
        "schema_version": "abel.input.v1",
        "batch_id": batch_id,
        "created_at": now_iso(),
        "source": "abel_classified.json",
        "api_calls": 0,
        "words": words,
        "instructions": {
            "processor": "Abel Chinese Education Engine",
            "output_schema": SCHEMA_VERSION,
            "write_result_to": "OUTBOX",
        },
    }
    atomic_write(inbox / f"{batch_id}.json", payload)
    print(f"exported {len(words)} words: {batch_id}")
    return len(words)


def fail_outbox(path, failed, reason):
    failed.mkdir(parents=True, exist_ok=True)
    target = failed / path.name
    if target.exists():
        target = failed / f"{path.stem}-{datetime.now().strftime('%Y%m%d-%H%M%S')}{path.suffix}"
    shutil.move(str(path), str(target))
    print(f"moved to FAILED: {path.name}: {reason}")


def validate_items(items):
    if not isinstance(items, list) or not items:
        return False, "items must be a non-empty list"

    seen = set()
    for item in items:
        if not isinstance(item, dict):
            return False, "each item must be an object"
        word_id = item.get("word_id")
        if word_id is None:
            return False, "missing word_id"
        key = str(word_id)
        if key in seen:
            return False, f"duplicate word_id: {word_id}"
        seen.add(key)
        if not isinstance(item.get("word"), str) or not item["word"].strip():
            return False, f"missing word for {word_id}"
        if not isinstance(item.get("education"), dict):
            return False, f"education must be an object for {word_id}"
    return True, ""


def import_outbox(outbox, archive, failed, inbox, done):
    imported = 0
    seen = {
        str(item.get("word_id")): item
        for item in done
        if isinstance(item, dict) and item.get("word_id") is not None
    }

    for path in sorted(outbox.glob("*.json")):
        try:
            payload = read_json(path, {})
        except SystemExit as exc:
            fail_outbox(path, failed, str(exc))
            continue

        if payload.get("schema_version") != SCHEMA_VERSION:
            fail_outbox(path, failed, "invalid schema_version")
            continue

        batch_id = payload.get("batch_id")
        items = payload.get("items")
        if not isinstance(batch_id, str) or not batch_id:
            fail_outbox(path, failed, "missing batch_id")
            continue

        valid, reason = validate_items(items)
        if not valid:
            fail_outbox(path, failed, reason)
            continue

        source = find_source_batch(inbox, archive, batch_id)
        if source is None:
            fail_outbox(path, failed, f"source batch not found: {batch_id}")
            continue

        source_payload = read_json(source, {})
        source_words = source_payload.get("words")
        if not isinstance(source_words, list):
            fail_outbox(path, failed, "source batch has no words list")
            continue

        allowed = {
            str(word.get("id"))
            for word in source_words
            if isinstance(word, dict) and word.get("id") is not None
        }
        output_ids = {str(item["word_id"]) for item in items}
        if not output_ids.issubset(allowed):
            unknown = sorted(output_ids - allowed)
            fail_outbox(path, failed, f"word_id not present in source batch: {unknown[:10]}")
            continue

        if output_ids != allowed:
            fail_outbox(path, failed, f"partial output: expected {len(allowed)}, got {len(output_ids)}")
            continue

        for item in items:
            seen[str(item["word_id"])] = item

        atomic_write(
            DST,
            {
                "schema_version": SCHEMA_VERSION,
                "updated_at": now_iso(),
                "api_calls": 0,
                "items": list(seen.values()),
            },
        )

        archive.mkdir(parents=True, exist_ok=True)
        target = archive / path.name
        if target.exists():
            target = archive / f"{path.stem}-{datetime.now().strftime('%Y%m%d-%H%M%S')}{path.suffix}"
        shutil.move(str(path), str(target))
        imported += len(items)
        print(f"imported {len(items)} words from {batch_id}")

    return imported


def acquire_lock():
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    handle = LOCK.open("w", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        raise SystemExit("Another Abel Drive bridge is already running")
    handle.write(str(os.getpid()))
    handle.flush()
    return handle


def main():
    lock_handle = acquire_lock()
    try:
        drive = root()
        inbox = drive / "INBOX"
        outbox = drive / "OUTBOX"
        archive = drive / "ARCHIVE"
        failed = drive / "FAILED"
        for path in (inbox, outbox, archive, failed):
            path.mkdir(parents=True, exist_ok=True)

        data = read_json(SRC, {"words": []})
        done_data = read_json(DST, {"items": []})
        done = done_data.get("items", [])
        exported = export_pending(inbox, data, done)
        imported = import_outbox(outbox, archive, failed, inbox, done)
        print(f"bridge complete: exported={exported}, imported={imported}, api_calls=0")
    finally:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        lock_handle.close()


if __name__ == "__main__":
    main()
