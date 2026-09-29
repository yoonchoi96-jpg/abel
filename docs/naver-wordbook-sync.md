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

## Local data

- Authenticated Chromium profile: `~/.naver_wordbook/browser_profile`
- Raw probe/sync snapshots: `~/.naver_wordbook/exports/`
- SQLite: `~/.naver_wordbook/naver_wordbook.sqlite3`
- Repository export: `data/naver_wordbook.json`

Never commit the browser profile or cookies.

## Schema

### wordbooks
Stable/discovered Naver wordbook metadata.

### words
Globally deduplicated word records.

### wordbook_words
Many-to-many membership between a word and a wordbook.

This lets downstream code query HSK 6 only, Netflix only, Taiwan travel only, HSK 5 ∩ HSK 6, or duplicate words across books without losing provenance.

## Workflow

The GitHub Actions workflow runs on a self-hosted Mac runner. The runner must have labels `self-hosted`, `macOS`, and `naver-wordbook`. GitHub supports custom runner labels and matches all requested labels cumulatively. citeturn0search0turn0search2

Schedule: 07:00 and 19:00 KST.

## First run

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
