#!/usr/bin/env python3
"""Abel <-> Google Drive bridge.

No Gemini API and no Google API calls are made here.
Abel only writes pending JSON batches to a local Google Drive sync folder
and imports completed JSON batches placed in OUTBOX by the user/Gemini.
"""
from pathlib import Path
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone

HOME = Path.home()
SRC = HOME / ".naver_wordbook/exports/abel_classified.json"
DST = HOME / ".naver_wordbook/exports/abel_gemini_education.json"
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
    return {str(item.get("word_id")) for item in done if item.get("word_id") is not None}


def pending_ids(inbox):
    ids = set()
    for path in inbox.glob("batch-*.json"):
        try:
            batch = read_json(path, {})
            for word in batch.get("words", []):
                if word.get("id") is not None:
                    ids.add(str(word["id"]))
        except SystemExit:
            raise
    return ids


def export_pending(inbox, data, done):
    completed = completed_ids(done)
    pending = pending_ids(inbox)
    words = [
        word for word in data.get("words", [])
        if word.get("id") is not None
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
            "write_result_to": "OUTBOX"
        },
    }
    atomic_write(inbox / f"batch-{stamp}.json", payload)
    print(f"exported {len(words)} words: {batch_id}")
    return len(words)


def import_outbox(outbox, archive, done):
    imported = 0
    seen = {str(item.get("word_id")): item for item in done if item.get("word_id") is not None}

    for path in sorted(outbox.glob("*.json")):
        payload = read_json(path, {})
        if payload.get("schema_version") != SCHEMA_VERSION:
            print(f"skip invalid schema: {path.name}")
            continue

        batch_id = payload.get("batch_id")
        items = payload.get("items")
        if not isinstance(batch_id, str) or not isinstance(items, list):
            print(f"skip invalid batch: {path.name}")
            continue

        batch_ids = set()
        valid = True
        for item in items:
            word_id = item.get("word_id") if isinstance(item, dict) else None
            if word_id is None or str(word_id) in batch_ids:
                valid = False
                break
            if "word" not in item or "education" not in item:
                valid = False
                break
            batch_ids.add(str(word_id))

        if not valid:
            print(f"skip malformed batch: {path.name}")
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
        target = archive / path.name
        if target.exists():
            target = archive / f"{path.stem}-{datetime.now().strftime('%Y%m%d-%H%M%S')}{path.suffix}"
        shutil.move(str(path), str(target))
        imported += len(items)
        print(f"imported {len(items)} words from {batch_id}")

    return imported


def main():
    drive = root()
    inbox = drive / "INBOX"
    outbox = drive / "OUTBOX"
    archive = drive / "ARCHIVE"
    for path in (inbox, outbox, archive):
        path.mkdir(parents=True, exist_ok=True)

    data = read_json(SRC, {"words": []})
    done_data = read_json(DST, {"items": []})
    done = done_data.get("items", [])
    export_pending(inbox, data, done)
    import_outbox(outbox, archive, done)


if __name__ == "__main__":
    main()
