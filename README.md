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

## Hanping ingestion boundary

Hanping is the vocabulary capture UI; Abel owns normalization and downstream enrichment.

The supported V1 path is **official/user-provided vocabulary export → local Abel normalization**:

1. Export vocabulary from Hanping using its supported Import/Export Vocab File feature.
2. Run `python scripts/hanping_ingest.py /path/to/export.txt`.
3. The normalized snapshot is written to `data/hanping/normalized.json`, which is intentionally git-ignored.
4. Feed that normalized data into the next Abel database/upstream enrichment stage once the actual Hanping export format has been verified.

The normalizer accepts JSON, CSV, TSV, and plain text and preserves starred state, tags, notes, traditional characters and pinyin when those fields are present.

Hanping account authentication, OTP handling, cookies, browser-session capture, and private cloud decryption are deliberately outside Abel.

## Naver data boundary

Abel intentionally does not automate access to the user's Naver account. It does not use GitHub Actions, a self-hosted runner, Playwright login, stored Naver sessions, or `NAVER_STORAGE_STATE_B64` to access the account.

The canonical repository input is `data/naver_wordbook.json`. Any future Naver-side collection must use a user-controlled and explicitly permitted mechanism, then import the resulting data into Abel.

Never put Naver passwords, cookies, storage state, or browser profiles in GitHub or GitHub Secrets.

## Commands

No Naver login, browser automation, session export, or collection command is part of the production Abel repository anymore. `data/naver_wordbook.json` is treated as an imported data boundary.

## Security

Never commit browser profiles, cookies, storage-state exports, or raw authentication material.

If Naver-side data needs to be refreshed, obtain/export it through a user-controlled and explicitly permitted mechanism, then update the data boundary. Abel itself must not automate the Naver account.
