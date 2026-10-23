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

from naver_wordbook_checkpoint import (
    digest as checkpoint_digest, load_cache, metadata as folder_metadata,
)
from naver_wordbook_parser import NaverSchemaError, build_snapshot, validate_folder_pages
from naver_wordbook_collect import (
    OUTPUT, CHECKPOINT, PROFILE, atomic_save_if_changed,
    fingerprint, load_folders,
)

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


def read_current_folder_index(profile=PROFILE, timeout_seconds=40):
    """Read ONLY the first-party folder index in the saved browser session.

    Never request card pages or replay the private JSON URL ourselves.
    No cookies, URLs, account texts or credentials are logged.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise NaverSchemaError("Playwright is not installed on this Mac") from exc
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch_persistent_context(
                user_data_dir=str(Path(profile).expanduser()),
                headless=True, viewport={"width": 1280, "height": 900})
            try:
                tab = browser.pages[0] if browser.pages else browser.new_page()
                folders, count = load_folders(tab, timeout_seconds * 1000)
                if count != len(folders):
                    raise NaverSchemaError("Live index has inconsistent folder count")
                return folders
            finally:
                browser.close()
    except NaverSchemaError:
        raise
    except Exception as exc:
        # Browser errors can contain URLs and account data. Never print raw text.
        raise NaverSchemaError(
            "Saved session could not read the folder index ({}); "
            "relogin may be needed".format(type(exc).__name__)) from None


def select_checkpoint_folders(entries, expected_count, current_folders=None):
    """Use EXACT current IDs, never arbitrarily pick latest N of stale cache."""
    if current_folders is None:
        if len(entries) != expected_count:
            raise NaverSchemaError(
                "Checkpoint has {} folders; last completed UI run had {}. "
                "Use --reconcile-index to compare the live folder list "
                "without re-scraping cards.".format(len(entries), expected_count))
        return sorted(entries.items())

    if len(current_folders) != expected_count:
        raise NaverSchemaError("Live folder index count differs from prior run")
    selected = []
    seen = set()
    for folder in current_folders:
        if not isinstance(folder, dict):
            raise NaverSchemaError("Invalid live folder index item")
        folder_id = folder.get("id")
        if not isinstance(folder_id, str) or not folder_id or folder_id in seen:
            raise NaverSchemaError("Duplicate/invalid folder in live index")
        seen.add(folder_id)
        record = entries.get(folder_id)
        if not isinstance(record, dict):
            raise NaverSchemaError(
                "A currently listed folder is missing from local checkpoint; "
                "an incremental refresh is required")
        if record.get("metadata") != folder_metadata(folder):
            raise NaverSchemaError(
                "A folder changed since its checkpoint was saved; "
                "an incremental refresh is required")
        selected.append((folder_id, record))
    return sorted(selected)


def snapshot_from_local_checkpoint(
    checkpoint_path, attempt_path, *, now=None, current_folders=None
):
    now = now or datetime.now(timezone.utc)
    expected_count, started_at = read_attempt(attempt_path)
    cache = load_cache(checkpoint_path)
    entries = cache["entries"]
    chosen = select_checkpoint_folders(entries, expected_count, current_folders)
    folders = []
    per_folder_pages = {}
    for folder_id, record in chosen:
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


def finalize(
    checkpoint_path=CHECKPOINT, attempt_path=None,
    output_dir=OUTPUT, *, current_folders=None,
):
    output_dir = Path(output_dir).expanduser()
    attempt_path = (Path(attempt_path).expanduser() if attempt_path is not None
                    else output_dir / "naver_wordbook_attempt.json")
    snapshot, collection_started = snapshot_from_local_checkpoint(
        checkpoint_path, attempt_path, current_folders=current_folders)
    content_digest = fingerprint(snapshot)
    live_index_verified = current_folders is not None
    full = dict(snapshot, source="naver_owner_local_checkpoint",
                verified_at=datetime.now(timezone.utc).isoformat(),
                origin_collection_started_at=collection_started,
                live_folder_index_verified=live_index_verified,
                not_live_freshness_check=not live_index_verified,
                digest=content_digest)
    priorities = {
        key: sum(w["priority"] == key for w in snapshot["words"])
        for key in ("P1", "P2", "P3", "P4")
    }
    summary = {
        "format": "abel.naver.sync_status.v2",
        "source": ("owner_local_checkpoint_reconciled"
                   if live_index_verified else "owner_local_checkpoint_offline"),
        "verified_at": full["verified_at"],
        "origin_collection_started_at": collection_started,
        "live_folder_index_verified": live_index_verified,
        "not_live_freshness_check": not live_index_verified,
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
    cli.add_argument("--reconcile-index", action="store_true",
                     help="read only live Naver folder index; no card-page rescrape")
    cli.add_argument("--profile-dir", type=Path, default=PROFILE)
    args = cli.parse_args()
    try:
        current_folders = None
        if args.reconcile_index:
            print("Checking Naver folder index only; NO word-card pages ...",
                  flush=True)
            current_folders = read_current_folder_index(args.profile_dir)
            print("Confirmed {} current folder IDs".format(
                len(current_folders)), flush=True)
        summary = finalize(
            checkpoint_path=args.checkpoint_path,
            attempt_path=args.attempt_path,
            output_dir=args.output_dir,
            current_folders=current_folders)
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
