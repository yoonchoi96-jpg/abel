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
    if status not in (0, 200, "200", "SUCCESS", "success"):
        raise NaverSchemaError("Unexpected Naver application status (no write)")
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


def load_cards_for_folder(page, folder, *, timeout_ms, pause_s):
    folder_id = folder["id"]
    responses = []
    expected_total = None
    expected_count = None
    page_number = 1
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
        if (total != expected_total or count != expected_count
                or total != folder["wordCount"]):
            raise NaverSchemaError("Word counts changed or disagree across pages")
        for item in items:
            if item.get("wordbookId") != folder_id:
                raise NaverSchemaError("Wordbook ID mismatch; aborting snapshot")
        responses.append(response)
        if sum(len(r["data"]["m_items"]) for r in responses) > MAX_CARDS:
            raise NaverSchemaError("Card safety cap exceeded")
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


def run(args):
    from playwright.sync_api import sync_playwright

    profile = Path(args.profile_dir).expanduser()
    output_dir = Path(args.output_dir).expanduser()
    if args.publish_to_drive:
        drive_dir = Path(args.drive_dir).expanduser()
        if not drive_dir.is_dir():
            raise NaverSchemaError("Drive destination must already exist on the Mac")
        if drive_dir.resolve() == profile.resolve() or profile.resolve() in drive_dir.resolve().parents:
            raise NaverSchemaError("Browser profile cannot be a Drive destination")
    else:
        drive_dir = None

    profile.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile), headless=False,
            viewport={"width": 1280, "height": 900})
        page = context.pages[0] if context.pages else context.new_page()
        try:
            page.goto(MAIN, wait_until="domcontentloaded", timeout=args.timeout * 1000)
            print("Log in to NAVER Chinese wordbook if required.")
            input("When the wordbook home screen is visible, press Enter: ")
            folders, total = load_folders(page, args.timeout * 1000)
            print("Verified {} wordbook folder index entries".format(total))
            per_folder = {}
            for n, folder in enumerate(folders, 1):
                # Do not print personal folder names/IDs to CI or public logs.
                print("Reading folder {}/{} ...".format(n, total))
                per_folder[folder["id"]] = load_cards_for_folder(
                    page, folder, timeout_ms=args.timeout * 1000,
                    pause_s=args.pause)
                time.sleep(args.pause)
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
    if dest.is_file():
        try:
            old = json.loads(dest.read_text(encoding="utf-8"))
            if old.get("digest") == digest and old.get("verified_card_pages") is True:
                print("No changes detected; existing verified snapshot retained")
                return summary
        except (OSError, ValueError):
            raise NaverSchemaError("Existing output is corrupted; refuse overwrite")
    changed = atomic_save_if_changed(dest, full)
    atomic_save_if_changed(output_dir / "naver_wordbook_status.json", summary)
    if drive_dir:
        # Only user-selected, already mounted local Drive folder is written.
        atomic_save_if_changed(drive_dir / dest.name, full)
        atomic_save_if_changed(drive_dir / "naver_wordbook_status.json", summary)
    print("Verified snapshot: {} (changed={})".format(dest, changed))
    print("Folders={} cards={} words={} priorities={}".format(
        total, snapshot["saved_card_count"], len(snapshot["words"]), priorities))
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
    try:
        run(args)
    except (NaverSchemaError, TimeoutError) as exc:
        raise SystemExit("INCOMPLETE: existing verified files unchanged. " + str(exc)) from exc


if __name__ == "__main__":
    main()
