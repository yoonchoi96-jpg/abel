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

## Data boundary

Naver account access is intentionally **outside** Abel's production automation boundary.

Abel does not use GitHub Actions, self-hosted runners, Playwright browser sessions, stored Naver cookies, or `NAVER_STORAGE_STATE_B64` to access the account. The canonical downstream input is `data/naver_wordbook.json`.

This keeps the Naver account separate from the GitHub automation plane. Any future Naver-side collection must use a user-controlled and explicitly permitted mechanism, then import the resulting data into Abel.

Never place Naver passwords, cookies, storage state, or browser profiles in GitHub.

## HSK 3.0

Abel also stores two non-Naver collections:

- `HSK 3.0 6급`: the user's requested 1,140 **new** Level-6 vocabulary items, with Korean meanings.
- `HSK 3.0 7–9급`: the combined advanced band of 5,600 items. The source list is complete; Korean gloss enrichment remains a separate data layer so source membership/counts remain stable.

The HSK database sync runs once daily at **07:00 KST**. It is idempotent by source + word + pinyin and writes into the same SQLite `words` / `wordbooks` / `wordbook_words` schema.
