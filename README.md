# Abel

Abel is the Naver Dictionary personal wordbook sync system.

## Core design

**Naver wordbook data → versioned GitHub JSON → downstream learning tools**

Naver account access is intentionally outside Abel's production automation path. Abel consumes the already-exported `data/naver_wordbook.json` as its canonical downstream input.

Abel also maintains two curated HSK 3.0 collections in the same SQLite database: **Level 6 new vocabulary (1,140)** and the combined **Level 7–9 advanced band (5,600)**.

Abel preserves **multiple Naver wordbooks as separate first-class collections** and keeps wordbook membership many-to-many. Words are globally deduplicated.

### Wordbooks

Examples include:
- 단어장
- Netflix 저장 단어장
- 대만 여행
- HSK 5급
- HSK 6급

A word appearing in HSK 5급 and HSK 6급 is stored once as a word and linked to both books.

HSK numbered Naver volumes are grouped: `신HSK_5급 필수단어 1~5탄` → `신HSK 5급`, and `신HSK_6급 필수단어 1~10탄` → `신HSK 6급`.

## HSK 3.0 collections

- `data/hsk30_level6_1140.csv`: the user's 1,140-new-word Level 6 list with Korean meanings.
- `data/hsk30_level7_9_5600.csv`: the combined 5,600-word Level 7–9 source list. Korean gloss enrichment is kept as a separate layer so source data is not overwritten.
- `scripts/hsk30_sync.py`: imports both collections into the same SQLite schema.
- `.github/workflows/hsk30-sync.yml`: scheduled daily at 07:00 KST.

## Hanping ingestion and automatic routing

Hanping is the vocabulary capture UI; Abel owns normalization, canonical identity and downstream routing.

Hanping's official Import/Export Vocab File feature is the supported machine-readable boundary. Cloud Backup remains a user-controlled backup feature; Abel does not log into Hanping or decrypt private cloud data.

The intended local flow is now:

```
Hanping
  ↓ official/user export
iCloud Drive / Downloads / Documents
  ↓ automatic local discovery
hanping_vocab_import.py
  ↓
hanping_db_sync.py
  ↓
hanping_router.py
  ├─ hsk30_level6
  ├─ hsk30_level7_9
  ├─ tocfl
  ├─ existing
  └─ new
  ↓
shared Abel SQLite
  ↓
Obsidian / downstream enrichment
```

The router consults the shared canonical DB using headword + pinyin when available, then falls back to deterministic existing-word matching. Hanping star/tag/note/traditional/pinyin data is preserved separately from canonical lexical data.

### One-command scan

```bash
python scripts/hanping_auto_sync.py
```

The watcher scans common Mac locations for new JSON/CSV/TSV/TXT exports and processes each content hash only once.

For continuous background polling:

```bash
python scripts/hanping_auto_sync.py --watch
```

A future macOS LaunchAgent can run the watcher automatically at login. No credentials are required.

The normalizer accepts JSON, CSV, TSV, and plain text. The normalized snapshot is written to `data/hanping/normalized.json`, which is intentionally git-ignored.

Hanping account authentication, OTP handling, cookies, browser-session capture, and private cloud decryption are deliberately outside Abel.

## Naver wordbook sync

Naver remains the primary vocabulary capture UI for Abel.

The production flow is:

```text
Naver 중국어 개인 단어장
  ↓ authenticated Chrome session on the user's Mac
scripts/naver_wordbook_sync.py
  ↓
SQLite + raw snapshots
  ↓
data/naver_wordbook.json
  ↓
Obsidian / downstream learning tools
```

The collector preserves multiple wordbooks as first-class collections, globally deduplicates words, and keeps many-to-many wordbook membership. HSK numbered Naver volumes are grouped into `신HSK 5급` and `신HSK 6급`.

### Commands

```bash
python scripts/naver_wordbook_sync.py --bootstrap
python scripts/naver_wordbook_sync.py --probe
python scripts/naver_wordbook_sync.py --sync
```

The authenticated browser profile stays on the user's Mac under `~/.naver_wordbook/browser_profile`. It is never committed to GitHub.

The scheduled workflow runs on the self-hosted Mac runner labeled `self-hosted`, `macOS`, and `naver-wordbook`.

## Security

Never commit browser profiles, cookies, storage-state exports, or raw authentication material.

If Naver-side data needs to be refreshed, obtain/export it through a user-controlled and explicitly permitted mechanism, then update the data boundary. Abel itself must not automate the Naver account.
