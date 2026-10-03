#!/usr/bin/env python3
"""Export the authenticated Naver Playwright session as compact storage state.

Run this once on the Mac where Abel's authenticated browser profile exists:
    python scripts/export_naver_storage_state.py > naver_storage_state.b64

The resulting base64 string is intended for a GitHub Actions secret named
NAVER_STORAGE_STATE_B64. Do not commit the output file.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

DATA_ROOT = Path(os.environ.get("NAVER_WORDBOOK_DATA", "~/.naver_wordbook")).expanduser()
PROFILE_DIR = DATA_ROOT / "browser_profile"

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        str(PROFILE_DIR),
        headless=True,
        viewport={"width": 1440, "height": 1000},
    )
    try:
        state = context.storage_state()
        raw = json.dumps(state, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        print(base64.b64encode(raw).decode("ascii"))
    finally:
        context.close()
