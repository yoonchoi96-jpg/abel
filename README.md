# Abel

Abel is the Naver Dictionary personal wordbook sync system.

## Core design

**Naver authenticated browser session → Playwright on Mac → raw snapshots + normalized SQLite → GitHub JSON export → GitHub Actions scheduled sync**

Abel preserves **multiple Naver wordbooks as separate first-class collections** and keeps wordbook membership many-to-many. Words are globally deduplicated.

### Wordbooks

Examples include:
- 단어장
- Netflix 저장 단어장
- 대만 여행
- HSK 5급
- HSK 6급

A word appearing in HSK 5급 and HSK 6급 is stored once as a word and linked to both books.

## Commands

```bash
python scripts/naver_wordbook_sync.py --bootstrap
python scripts/naver_wordbook_sync.py --probe
python scripts/naver_wordbook_sync.py --sync
```

## Security

The Naver password is never stored by Abel. The authenticated browser profile stays on the Mac and must never be committed.

GitHub Actions uses a self-hosted Mac runner because the authenticated browser state is local.