# Naver Dictionary Wordbook Sync

## Goal

Keep a machine-readable copy of the user's Naver Dictionary personal wordbook synchronized with Abel without storing Naver credentials in GitHub.

## Security model

The Naver login is performed once in a persistent Chromium profile on the user's Mac. The password is never read by Abel and the profile must never be committed.

GitHub Actions runs on a self-hosted Mac runner. This is deliberate: a GitHub-hosted runner would not have the user's persistent authenticated browser session.

## First run

    cd ~/abel
    python3 -m venv .venv
    source .venv/bin/activate
    pip install playwright
    python -m playwright install chromium
    python scripts/naver_wordbook_sync.py --bootstrap

During bootstrap, log in to Naver and open the personal wordbook until its entries are visible, then press Enter.

After login:

    python scripts/naver_wordbook_sync.py --probe

Probe mode records DOM cards and relevant JSON/network responses under ~/.naver_wordbook/exports/. This verifies the current Naver SPA structure before scheduled synchronization.

## Normal synchronization

    python scripts/naver_wordbook_sync.py --sync

The canonical repository export is data/naver_wordbook.json.

Local persistence is ~/.naver_wordbook/naver_wordbook.sqlite3.

## GitHub Actions

The workflow uses a self-hosted runner with labels:

- self-hosted
- macOS
- naver-wordbook

Schedule: 07:00 and 19:00 KST.

Manual dispatch supports sync and probe.

## Data design

Raw capture is retained separately from normalized fields. The normalized record is designed to support later enrichment without overwriting source data:

- word
- meaning
- pronunciation
- part of speech
- example
- wordbook
- source URL
- first_seen
- last_seen
- raw source
