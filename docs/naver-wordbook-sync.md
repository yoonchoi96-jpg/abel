# Abel — Naver Wordbook Sync

Abel keeps a machine-readable copy of the user's Naver Dictionary personal wordbooks.

## Multi-wordbook model

Naver wordbooks are **not flattened** into one category. Abel preserves each wordbook and the many-to-many relationship between wordbooks and words.

Examples:
- 단어장
- Netflix 저장 단어장
- 대만 여행
- HSK 5급
- HSK 6급

A word may belong to multiple wordbooks. Global word records are deduplicated while membership is preserved.

Naver's `신HSK_6급 필수단어 1~10탄` are grouped into `신HSK 6급`; `신HSK_5급 필수단어 1~5탄` are grouped into `신HSK 5급`.

## Local data

- Authenticated browser profile: `~/.naver_wordbook/browser_profile` (manual Mac fallback only)
- Raw probe/sync snapshots: `~/.naver_wordbook/exports/`
- SQLite: `~/.naver_wordbook/naver_wordbook.sqlite3`
- Repository export: `data/naver_wordbook.json`

Never commit the browser profile or cookies.

## Canonical GitHub-hosted workflow

The canonical workflow is:

```
Authenticated Naver browser
        ↓
NAVER_STORAGE_STATE_B64 GitHub secret
        ↓
GitHub-hosted Ubuntu runner
        ↓
Playwright Chromium
        ↓
data/naver_wordbook.json
```

Workflow: `.github/workflows/naver-wordbook-sync-hosted.yml`

Modes:
- `probe`: validates the session and collects diagnostics without changing the canonical JSON.
- `sync`: collects wordbooks, updates SQLite/export data, and commits `data/naver_wordbook.json` when it changes.

The workflow is currently manual-dispatch until the authenticated storage-state secret is proven stable. This avoids scheduling repeated failures when the Naver session is missing or expired.

Before collection, the workflow validates that `NAVER_STORAGE_STATE_B64` is present and is valid base64-encoded Playwright storage state.

## Authentication lifecycle

Abel never stores the Naver password.

GitHub-hosted runners are ephemeral, so Naver authentication is restored from `NAVER_STORAGE_STATE_B64`. The storage state must originate from an already-authenticated Naver browser session.

If Naver authentication expires:
1. Open an authenticated Naver browser session on a machine where the Naver login is available.
2. Export a fresh Playwright storage state with `scripts/export_naver_storage_state.py`.
3. Replace the repository secret `NAVER_STORAGE_STATE_B64`.
4. Run the hosted workflow in `probe` mode first.
5. Run `sync` only after the probe succeeds.

Never commit the storage-state output.

## Legacy Mac fallback

The former Mac self-hosted workflow is retained only as a manual fallback:

`.github/workflows/naver-wordbook-sync.yml`

It requires runner labels:
- `self-hosted`
- `macOS`
- `naver-wordbook`

It is not the canonical scheduled path.

## First-run / recovery on Mac

```bash
cd ~/abel
python3 -m venv .venv
source .venv/bin/activate
pip install playwright
python -m playwright install chromium
python scripts/naver_wordbook_sync.py --bootstrap
python scripts/naver_wordbook_sync.py --probe
```

Probe output is intentionally retained before production sync so the current Naver SPA/API structure can be hardened without losing evidence.

## HSK 3.0

Abel also stores two non-Naver collections:

- `HSK 3.0 6급`: the user's requested 1,140 **new** Level-6 vocabulary items, with Korean meanings.
- `HSK 3.0 7–9급`: the combined advanced band of 5,600 items. The source list is complete; Korean gloss enrichment remains a separate data layer so source membership/counts remain stable.

The HSK database sync runs once daily at **07:00 KST**. It is idempotent by source + word + pinyin and writes into the same SQLite `words` / `wordbooks` / `wordbook_words` schema.
