# Abel

Abel is the Naver Dictionary personal wordbook sync system.

## Core design

**Naver authenticated browser session → Playwright/Chrome on Mac → raw snapshots + normalized SQLite → GitHub JSON export → Obsidian**

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

## Browser

Abel uses a dedicated persistent browser profile, not the user's everyday Chrome profile. `NAVER_BROWSER=chrome` is the default; Chromium remains available as a fallback.

## Commands

```bash
python scripts/naver_wordbook_sync.py --bootstrap
python scripts/naver_wordbook_sync.py --probe
python scripts/naver_wordbook_sync.py --sync
```

## Security

The Naver password is never stored by Abel. The authenticated browser profile stays on the Mac and must never be committed.

GitHub Actions uses a self-hosted Mac runner because the authenticated browser state is local.