#!/usr/bin/env python3
"""Recover a complete local Naver wordbook snapshot without opening a browser.

Only reads the owner-local, already saved per-folder checkpoints. No Naver
requests, cookies, API replay, or Google Drive uploads are performed.
Unrecognized card content stays preserved in the private source checkpoint
and is marked unresolved, NEVER silently dropped or guessed.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from naver_wordbook_checkpoint import digest as checkpoint_digest, load_cache
from naver_wordbook_parser import NaverSchemaError, build_snapshot, validate_folder_pages
from naver_wordbook_collect import OUTPUT, CHECKPOINT, atomic_save_if_changed, fingerprint

MAX_CHECKPOINT_AGE = timedelta(days=7)


def read_attempt(path):
    try:
        report = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise NaverSchemaError("Missing/invalid local collection attempt metadata") from exc
    if (not isinstance(report, dict)
            or report.get("format") != "abel.naver.collect_attempt.v1"):
        raise NaverSchemaError("Attempt report has unexpected structure")
    completed = report.get("completed_folders")
    total = report.get("folder_count")
    if (type(total) is not int or total <= 0 or type(completed) is not int
            or completed != total):
        raise NaverSchemaError(
            "Previous attempt did not finish all folder page collections")
    if report.get("stage") not in (
        "INCOMPLETE", "FINISHED", "FINISHED_WITH_UNRESOLVED",
    ):
        raise NaverSchemaError("Unrecognized attempt state")
    if (report["stage"] == "INCOMPLETE"
            and report.get("error_stage") != "VERIFYING_ALL_PAGES"):
        raise NaverSchemaError(
            "Previous attempt failed before all pages were validated")
    return total, report.get("started_at")


def snapshot_from_local_checkpoint(checkpoint_path, attempt_path, *, now=None):
    now = now or datetime.now(timezone.utc)
    expected_count, started_at = read_attempt(attempt_path)
    cache = load_cache(checkpoint_path)
    entries = cache["entries"]
    if len(entries) != expected_count:
        raise NaverSchemaError(
            "Checkpoint folder count does not match last completed UI collection")
    folders = []
    per_folder_pages = {}
    for folder_id, record in sorted(entries.items()):
        if not isinstance(record, dict):
            raise NaverSchemaError("Malformed private folder checkpoint")
        meta = record.get("metadata")
        pages = record.get("pages")
        if not isinstance(meta, dict) or meta.get("id") != folder_id:
            raise NaverSchemaError("Folder checkpoint identity mismatch")
        if not isinstance(pages, list) or record.get("digest") != checkpoint_digest(pages):
            raise NaverSchemaError("Private cached page digest mismatch")
        try:
            stored = datetime.fromisoformat(record["stored_at"])
        except (KeyError, ValueError, TypeError) as exc:
            raise NaverSchemaError("Missing private checkpoint timestamp") from exc
        if (stored.tzinfo is None or stored > now
                or now - stored > MAX_CHECKPOINT_AGE):
            raise NaverSchemaError(
                "Checkpoint is too old or timestamp invalid: browser refresh required")
        folder = {key: meta.get(key) for key in ("id", "name", "wordCount")}
        validate_folder_pages(folder_id, pages, folder["wordCount"])
        folders.append(folder)
        per_folder_pages[folder_id] = pages
    snapshot = build_snapshot(
        folders, per_folder_pages, reported_folder_count=expected_count)
    return snapshot, started_at


def finalize(checkpoint_path=CHECKPOINT, attempt_path=None, output_dir=OUTPUT):
    output_dir = Path(output_dir).expanduser()
    attempt_path = (Path(attempt_path).expanduser() if attempt_path is not None
                    else output_dir / "naver_wordbook_attempt.json")
    snapshot, collection_started = snapshot_from_local_checkpoint(
        checkpoint_path, attempt_path)
    content_digest = fingerprint(snapshot)
    full = dict(snapshot, source="naver_owner_local_checkpoint",
                verified_at=datetime.now(timezone.utc).isoformat(),
                origin_collection_started_at=collection_started,
                not_live_freshness_check=True, digest=content_digest)
    priorities = {
        key: sum(w["priority"] == key for w in snapshot["words"])
        for key in ("P1", "P2", "P3", "P4")
    }
    summary = {
        "format": "abel.naver.sync_status.v2",
        "source": "owner_local_checkpoint_offline",
        "verified_at": full["verified_at"],
        "origin_collection_started_at": collection_started,
        "not_live_freshness_check": True,
        "collection_complete": True,
        "classification_complete": snapshot["classification_complete"],
        "complete": snapshot["classification_complete"],
        "priority_counts_provisional": snapshot["priority_counts_provisional"],
        "unresolved_card_count": snapshot["unresolved_card_count"],
        "folder_count": snapshot["folder_count"],
        "saved_card_count": snapshot["saved_card_count"],
        "distinct_words": len(snapshot["words"]),
        "priorities": priorities,
        "sha256": content_digest,
    }
    target = output_dir / "naver_wordbook_verified.json"
    if target.is_file():
        try:
            old = json.loads(target.read_text(encoding="utf-8"))
            if old.get("digest") == content_digest:
                canonical_old = {key: old.get(key) for key in snapshot}
                if fingerprint(canonical_old) != content_digest:
                    raise NaverSchemaError("Existing snapshot integrity mismatch")
                full = old
                summary["verified_at"] = old["verified_at"]
                atomic_save_if_changed(
                    output_dir / "naver_wordbook_status.json", summary)
                return summary
        except (OSError, UnicodeError, ValueError, TypeError) as exc:
            raise NaverSchemaError(
                "Existing verified snapshot is corrupt; refusing overwrite") from exc

    atomic_save_if_changed(target, full)
    atomic_save_if_changed(output_dir / "naver_wordbook_status.json", summary)
    return summary


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--checkpoint-path", type=Path, default=CHECKPOINT)
    cli.add_argument("--attempt-path", type=Path)
    cli.add_argument("--output-dir", type=Path, default=OUTPUT)
    args = cli.parse_args()
    try:
        summary = finalize(
            checkpoint_path=args.checkpoint_path,
            attempt_path=args.attempt_path,
            output_dir=args.output_dir)
    except NaverSchemaError as exc:
        raise SystemExit("OFFLINE FINALIZE INCOMPLETE: " + str(exc)) from None
    print("FULL CARD COLLECTION: {}/{} folders verified".format(
        summary["folder_count"], summary["folder_count"]))
    print("SAVED CARDS: {}".format(summary["saved_card_count"]))
    print("CLASSIFIED WORDS: {}".format(summary["distinct_words"]))
    print("UNRESOLVED CARDS: {}".format(summary["unresolved_card_count"]))
    if summary["unresolved_card_count"]:
        print("Classification is partial; P1-P4 counts are PROVISIONAL.")
        print("Original unresolved card JSON stays in the private checkpoint.")
    print("STATUS: {}".format(Path(args.output_dir).expanduser()
                              / "naver_wordbook_status.json"))
    print("OUTPUT: {}".format(Path(args.output_dir).expanduser()
                              / "naver_wordbook_verified.json"))


if __name__ == "__main__":
    main()
