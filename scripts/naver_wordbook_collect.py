#!/usr/bin/env python3
"""Owner-local, UI-driven Naver Chinese wordbook snapshot (opt-in).

NO direct/undocumented API replay. This visits Naver's wordbook pages in
the owner's own Chromium window, observes the normal first-party JSON
responses, and builds an offline, validated snapshot. It never writes to
Naver and never exports the Chromium session profile or HTTP headers.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit

from naver_wordbook_parser import NaverSchemaError, build_snapshot

MAIN = "https://learn.dict.naver.com/wordbook/zhkodict/#/my/main"
ORIGIN = "learn.dict.naver.com"
FOLDER_PATH = "/gateway-api/zhkodict/mywordbook/wordbook/list.dict"
CARD_PATH = "/gateway-api/zhkodict/mywordbook/word/list/search"
PROFILE = Path.home() / "Library/Application Support/Abel/NaverProfile"
OUTPUT = Path.home() / "Documents/Abel_Naver_Wordbook"
MAX_FOLDERS = 500
MAX_CARDS = 100_000
MAX_PAGES_PER_FOLDER = 300
MAX_RESPONSE_BYTES = 8_000_000


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def matches_response(response, endpoint, *, folder_id=None):
    try:
        p = urlsplit(response.url)
        if (p.scheme != "https" or p.hostname != ORIGIN
                or p.path != endpoint or response.request.method != "GET"):
            return False
        if folder_id is not None:
            return parse_qs(p.query).get("wbId") == [folder_id]
        return True
    except Exception:
        return False


def is_paginated_wordbook_payload(payload):
    """Strict structural gate for observed Naver meta.status=1 responses.

    The first-party UI returned status 1 in a HTTP-200 folder response.
    That alone does not prove success. Require the full folder/card page
    envelope, leaving detailed page and identity checks to callers.
    """
    if not isinstance(payload, dict):
        return False
    data = payload.get("data")
    if not isinstance(data, dict):
        return False
    items = data.get("m_items")
    if not isinstance(items, list) or not all(isinstance(x, dict) for x in items):
        return False
    total = data.get("m_total")
    if type(total) is not int or total < 0:
        return False
    for page_key, count_key in (
        ("m_page", "m_totalPage"),
        ("m_current_page", "m_total_pages"),
    ):
        page, pages = data.get(page_key), data.get(count_key)
        if (type(page) is int and type(pages) is int
                and page >= 0 and pages >= 0):
            return True
    return False


def safe_response_json(response):
    if response.status != 200:
        raise NaverSchemaError("Naver returned HTTP {} for a read".format(response.status))
    ctype = response.headers.get("content-type", "")
    if "json" not in ctype.lower():
        raise NaverSchemaError("Naver returned a non-JSON response")
    declared = response.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_RESPONSE_BYTES:
        raise NaverSchemaError("Response exceeded the safety size cap")
    body = response.body()
    if len(body) > MAX_RESPONSE_BYTES:
        raise NaverSchemaError("Response exceeded the safety size cap")
    try:
        data = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise NaverSchemaError("Naver response was not valid JSON") from exc
    if not isinstance(data, dict):
        raise NaverSchemaError("Expected a JSON object")
    # A successful HTTP response need not mean successful application data.
    meta = data.get("meta")
    if not isinstance(meta, dict):
        raise NaverSchemaError("No application response metadata")
    status = meta.get("status")
    # bool is a Python int subtype; false must not be mistaken for 0.
    known_success = (
        (type(status) is int and status in (0, 200))
        or (type(status) is str and status in ("200", "SUCCESS", "success"))
    )
    # A real authenticated UI response used meta.status=1. Accept that
    # observation ONLY for structurally valid paginated folder/card data.
    # Other status values (including 1 with an error-shaped body) still fail.
    if type(status) is int and status == 1:
        known_success = is_paginated_wordbook_payload(data)
    if not known_success:
        # The service's private application codes are undocumented. The
        # numeric *code* is safe to reveal; meta.message is not (it may
        # contain account-specific text) and must never be logged.
        if type(status) is int and -999999 <= status <= 999999:
            code = str(status)
        else:
            code = "nonstandard_type_" + type(status).__name__
        raise NaverSchemaError(
            "Unrecognized Naver application status code: {}. "
            "HTTP 200 alone does NOT establish application success; "
            "no snapshot was written.".format(code))
    return data


def require_page(data, *, collection, expected_page=None):
    root = data.get("data")
    if not isinstance(root, dict):
        raise NaverSchemaError("Missing data object in {}".format(collection))
    items = root.get("m_items")
    if not isinstance(items, list) or not all(isinstance(x, dict) for x in items):
        raise NaverSchemaError("Missing JSON items in {}".format(collection))
    folder = collection == "folders"
    total_key = "m_total"
    page_key = "m_page" if folder else "m_current_page"
    pages_key = "m_totalPage" if folder else "m_total_pages"
    total, number, page_count = root.get(total_key), root.get(page_key), root.get(pages_key)
    if any(type(x) is not int for x in (total, number, page_count)):
        raise NaverSchemaError("Noninteger pagination fields in {}".format(collection))
    if total < 0 or number < 0 or page_count < 0:
        raise NaverSchemaError("Negative pagination field in {}".format(collection))
    if expected_page is not None and number != expected_page:
        # Naver may return index zero for a genuinely empty wordbook.
        if not (collection == "cards" and expected_page == 1
                and total == 0 and page_count == 0 and number == 0):
            raise NaverSchemaError("UI route did not open expected page of {}".format(collection))
    return items, total, number, page_count


def cards_url(folder, page_number):
    folder_id = folder["id"]
    name = folder["name"]
    if not isinstance(folder_id, str) or not folder_id:
        raise NaverSchemaError("Folder ID absent")
    if not isinstance(name, str) or not name:
        raise NaverSchemaError("Folder name absent")
    return (
        "https://learn.dict.naver.com/wordbook/zhkodict/"
        "#/my/cards?wbId={}&qt=0&st=0&name={}&tab=list&page={}"
    ).format(quote(folder_id, safe=""), quote(name, safe=""), page_number)


def load_folders(page, timeout_ms):
    # For a fresh page load, wait for the browser's OWN folder-list request.
    with page.expect_response(
        lambda r: matches_response(r, FOLDER_PATH), timeout=timeout_ms
    ) as expected:
        page.goto(MAIN, wait_until="domcontentloaded", timeout=timeout_ms)
    payload = safe_response_json(expected.value)
    items, total, index, pages = require_page(payload, collection="folders")
    if total > MAX_FOLDERS or pages > MAX_FOLDERS:
        raise NaverSchemaError("Too many folder pages; safety stop")
    if pages != 1 or len(items) != total:
        # UI folder-page routing is not verified: fail closed rather than silently omit.
        raise NaverSchemaError("Multiple/incomplete folder-list pages are unsupported")
    folders = []
    for item in items:
        folder_id = item.get("id")
        name = item.get("name")
        count = item.get("wordCount")
        if not isinstance(folder_id, str) or not folder_id:
            raise NaverSchemaError("Invalid saved-folder ID")
        if not isinstance(name, str) or not name:
            raise NaverSchemaError("Invalid saved-folder name")
        if type(count) is not int or count < 0:
            raise NaverSchemaError("Invalid saved-folder count")
        folders.append({"id": folder_id, "name": name, "wordCount": count})
    if len({x["id"] for x in folders}) != total:
        raise NaverSchemaError("Folder list includes duplicate IDs")
    return folders, total


def load_cards_for_folder(page, folder, *, timeout_ms, pause_s,
                          page_progress=lambda **details: None):
    folder_id = folder["id"]
    responses = []
    expected_total = None
    expected_count = None
    page_number = 1
    accumulated_cards = 0
    while True:
        if len(responses) >= MAX_PAGES_PER_FOLDER:
            raise NaverSchemaError("Too many pages; safety stop")
        with page.expect_response(
            lambda r: matches_response(r, CARD_PATH, folder_id=folder_id),
            timeout=timeout_ms,
        ) as expected:
            page.goto(cards_url(folder, page_number),
                      wait_until="domcontentloaded", timeout=timeout_ms)
        response = safe_response_json(expected.value)
        items, total, returned, count = require_page(
            response, collection="cards", expected_page=page_number)
        if expected_total is None:
            expected_total = total
            expected_count = count
            if count > MAX_PAGES_PER_FOLDER:
                raise NaverSchemaError("Folder exceeds the page safety cap")
        if (total != expected_total or count != expected_count
                or total != folder["wordCount"]):
            raise NaverSchemaError("Word counts changed or disagree across pages")
        for item in items:
            if item.get("wordbookId") != folder_id:
                raise NaverSchemaError("Wordbook ID mismatch; aborting snapshot")
        accumulated_cards += len(items)
        if accumulated_cards > expected_total or accumulated_cards > MAX_CARDS:
            raise NaverSchemaError("Card count exceeds declared/safety total")
        responses.append(response)
        # Nothing private: report the numeric position/volume only.
        page_progress(page_index=page_number, page_count=max(1, count),
                      cards_read=accumulated_cards, cards_expected=total)
        if page_number >= max(1, count):
            break
        page_number += 1
        time.sleep(pause_s)
    return responses


def fingerprint(snapshot):
    # No timestamp changes in the fingerprint: skip unchanged snapshots.
    canonical = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def atomic_save_if_changed(destination, payload):
    destination = Path(destination).expanduser()
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    new_json = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if destination.exists() and destination.read_text(encoding="utf-8") == new_json:
        return False
    fd, tmp = tempfile.mkstemp(prefix=".abel-", suffix=".tmp", dir=parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            os.fchmod(handle.fileno(), 0o600)
            handle.write(new_json)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, destination)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return True


def run(args, progress=lambda stage, **details: None):
    from playwright.sync_api import sync_playwright

    progress("CHECKING_DESTINATION")

    profile = Path(args.profile_dir).expanduser()
    output_dir = Path(args.output_dir).expanduser()
    if args.publish_to_drive:
        drive_dir = Path(args.drive_dir).expanduser()
        if not drive_dir.is_dir():
            raise NaverSchemaError("Drive destination must already exist on the Mac")
        drive_root = drive_dir.resolve()
        private_profile = profile.resolve()
        if (drive_root == private_profile
                or private_profile in drive_root.parents
                or drive_root in private_profile.parents):
            raise NaverSchemaError("Browser profile and Drive paths must not overlap")
    else:
        drive_dir = None

    progress("OPENING_BROWSER")
    profile.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile), headless=False,
            viewport={"width": 1280, "height": 900})
        page = context.pages[0] if context.pages else context.new_page()
        try:
            page.goto(MAIN, wait_until="domcontentloaded", timeout=args.timeout * 1000)
            progress("WAITING_FOR_LOGIN")
            print("Log in to NAVER Chinese wordbook if required.")
            input("When the wordbook home screen is visible, press Enter: ")
            progress("READING_FOLDER_INDEX")
            folders, total = load_folders(page, args.timeout * 1000)
            progress("FOLDER_INDEX_READY", folder_count=total)
            print("Verified {} wordbook folder index entries".format(total))
            per_folder = {}
            for n, folder in enumerate(folders, 1):
                # Do not print personal folder names/IDs to CI or public logs.
                progress("READING_FOLDER_CARDS", folder_index=n,
                         folder_count=total, completed_folders=n - 1)
                print("Reading folder {}/{} ...".format(n, total))
                def page_progress(*, page_index, page_count,
                                  cards_read, cards_expected):
                    progress("READING_CARD_PAGE", folder_index=n,
                             folder_count=total, completed_folders=n - 1,
                             page_index=page_index, page_count=page_count,
                             cards_read=cards_read, cards_expected=cards_expected)
                    print("  Folder {}/{} | page {}/{} | cards {}/{}".format(
                        n, total, page_index, page_count, cards_read,
                        cards_expected), flush=True)

                per_folder[folder["id"]] = load_cards_for_folder(
                    page, folder, timeout_ms=args.timeout * 1000,
                    pause_s=args.pause, page_progress=page_progress)
                progress("FOLDER_COMPLETE", folder_index=n,
                         folder_count=total, completed_folders=n,
                         page_index=0, page_count=0,
                         cards_read=0, cards_expected=0)
                time.sleep(args.pause)
            progress("VERIFYING_ALL_PAGES", completed_folders=total)
            snapshot = build_snapshot(
                folders, per_folder, reported_folder_count=total)
        finally:
            context.close()

    # Only this point can publish new data. Any exception above leaves old files untouched.
    digest = fingerprint(snapshot)
    priorities = {
        label: sum(x["priority"] == label for x in snapshot["words"])
        for label in ("P1", "P2", "P3", "P4")
    }
    full = dict(snapshot, source="naver_owner_local_ui",
                verified_at=now_iso(), digest=digest)
    summary = {
        "format": "abel.naver.sync_status.v1", "verified_at": full["verified_at"],
        "complete": True, "folder_count": total,
        "saved_card_count": snapshot["saved_card_count"],
        "distinct_words": len(snapshot["words"]),
        "priorities": priorities, "sha256": digest,
    }

    dest = output_dir / "naver_wordbook_verified.json"
    # Reuse timestamp on an unchanged snapshot to avoid redundant writes.
    existing_unchanged = False
    if dest.is_file():
        try:
            old = json.loads(dest.read_text(encoding="utf-8"))
            if not isinstance(old, dict):
                raise ValueError("Snapshot must be an object")
            existing_unchanged = (
                old.get("digest") == digest
                and old.get("verified_card_pages") is True)
            if existing_unchanged:
                # Verify the existing payload actually matches its stored digest.
                canonical_old = {
                    key: old.get(key) for key in snapshot
                }
                if fingerprint(canonical_old) != digest:
                    raise ValueError("Saved snapshot digest does not match content")
                # Preserve the original verification timestamp on unchanged data.
                full = old
                summary["verified_at"] = old["verified_at"]
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise NaverSchemaError(
                "Existing output is corrupted; refuse overwrite") from exc
    progress("WRITING_VERIFIED_SNAPSHOT", completed_folders=total)
    changed = False if existing_unchanged else atomic_save_if_changed(dest, full)
    atomic_save_if_changed(output_dir / "naver_wordbook_status.json", summary)
    if drive_dir:
        progress("PUBLISHING_DRIVE_COPY")
        # An existing local snapshot can still be published on an unchanged run.
        # Never upload browser profiles, cookies or the raw HTTP responses.
        atomic_save_if_changed(drive_dir / dest.name, full)
        atomic_save_if_changed(drive_dir / "naver_wordbook_status.json", summary)
    print("Verified snapshot: {} (changed={})".format(dest, changed))
    print("Folders={} cards={} words={} priorities={}".format(
        total, snapshot["saved_card_count"], len(snapshot["words"]), priorities))
    progress("FINISHED", complete=True, folder_count=total,
             saved_card_count=snapshot["saved_card_count"],
             distinct_words=len(snapshot["words"]))
    return summary


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--profile-dir", type=Path, default=PROFILE)
    cli.add_argument("--output-dir", type=Path, default=OUTPUT)
    cli.add_argument("--timeout", type=int, default=40)
    cli.add_argument("--pause", type=float, default=1.0)
    cli.add_argument("--drive-dir", type=Path)
    cli.add_argument("--publish-to-drive", action="store_true")
    args = cli.parse_args()
    if args.publish_to_drive and not args.drive_dir:
        cli.error("--publish-to-drive requires --drive-dir")
    if args.timeout < 10 or args.pause < 0.7:
        cli.error("Use timeout >= 10s and pause >= 0.7s to avoid excessive traffic")
    if args.profile_dir.expanduser().resolve() == args.output_dir.expanduser().resolve():
        cli.error("Browser profile cannot be the snapshot output directory")
    # Always emit a small non-sensitive attempt status, even if collection fails.
    # Never export word values, wordbook names, IDs, cookies, URLs or raw errors.
    diagnostic = args.output_dir.expanduser() / "naver_wordbook_attempt.json"
    attempt = {
        "format": "abel.naver.collect_attempt.v1",
        "started_at": now_iso(),
        "stage": "STARTING", "complete": False,
        "folder_count": None, "folder_index": 0,
        "completed_folders": 0, "page_index": 0, "page_count": 0,
        "cards_read": 0, "cards_expected": 0,
    }

    def progress(stage, **details):
        attempt.update(details)
        attempt["stage"] = stage
        attempt["updated_at"] = now_iso()
        atomic_save_if_changed(diagnostic, attempt)
        print("ABEL_STAGE: {} ({}/{})".format(
            stage, attempt["completed_folders"],
            attempt["folder_count"] if attempt["folder_count"] is not None else "?"),
            flush=True)

    progress("STARTING")
    try:
        run(args, progress=progress)
    except KeyboardInterrupt:
        failed_stage = attempt["stage"]
        progress("CANCELLED", error_stage=failed_stage,
                 error_category="UserCancelled",
                 error_message="Stopped by owner before verification")
        raise SystemExit("CANCELLED: no verified snapshot was written.") from None
    except NaverSchemaError as exc:
        failed_stage = attempt["stage"]
        progress("INCOMPLETE", error_stage=failed_stage,
                 error_category="NaverSchemaError",
                 error_message=str(exc))
        raise SystemExit(
            "INCOMPLETE: existing verified data unchanged. "
            "See naver_wordbook_attempt.json; error: " + str(exc)) from None
    except Exception as exc:
        failed_stage = attempt["stage"]
        progress("INCOMPLETE", error_stage=failed_stage,
                 error_category=type(exc).__name__,
                 error_message="Browser/IO exception (details intentionally omitted)")
        raise SystemExit(
            "INCOMPLETE: existing verified data unchanged. "
            "See naver_wordbook_attempt.json; exception type: "
            + type(exc).__name__) from None


if __name__ == "__main__":
    main()
