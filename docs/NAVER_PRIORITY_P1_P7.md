# Abel: experimental P1-P7 curated-vocabulary priorities

Status: **implemented as an owner-local offline PREVIEW, not activated in production**.

## Motivation

Owner's authenticated Mac collection on 2026-10-23:
- 19 complete wordbook folders
- 5,878 saved cards
- 4,892 distinct parsed words under original all-folder P1-P4 grouping
- 45 unsupported card formats preserved separately
- Prior P4: 4,079 / 4,892 (83.4%) - too concentrated

These are the **old** figures, not the new P1-P7 distribution.

## New ranking

| Priority | Condition |
|---|---|
| P1 | A word appears in >=4 **distinct user-curated** wordbooks |
| P2 | In 3 curated wordbooks |
| P3 | In 2 curated wordbooks |
| P4 | In exactly 1 curated wordbook and a saved numbered legacy HSK 5 reference list |
| P5 | In 1 curated wordbook and legacy HSK 6 reference OR Abel HSK 3.0 level-6 *new vocabulary* list |
| P6 | In 1 curated wordbook and Abel HSK 3.0 level-7-to-9 vocabulary |
| P7 | In 1 curated wordbook, but unmatched in these source lists; HSK level `null` / unknown |

Tier conflict precedence: **5, then 6, then 7-9** for single-folder entries.
Curated-folder duplicates always outrank the tier lookup. Repeated cards
within the same folder do not count as duplicates.

### Important data distinctions

- Exact `신HSK_5급 필수단어 N탄` and `신HSK_6급 필수단어 N탄` folders
  are **reference lists only**, excluded from curated-folder counts.
  Generic personal folders such as `HSK 6급 개인암기` remain curated.
- The repo currently has `data/hsk30_level6_1140.csv` (1140 *new*
  HSK 3.0 level-6 items) and `data/hsk30_level7_9_5600.csv`
  (5600 advanced-band rows). It does **not** currently have a complete
  HSK 3.0 level-5 master list.
- The P4 legacy list and P5 mixed legacy/3.0 sources are not a
  standards-consistent HSK 3.0 classification. Use `hsk_reference_sources`
  and `hsk_match_quality=headword_only` when presenting results.
- P7 is **not** synonymous with HSK 1-4, basic, easy, or unimportant.
  It includes unmatched levels and source gaps.
- Unparseable cards are **not** forced into P7. They remain unclassified
  and make `priority_counts_provisional=true`.
- This output contains private words and card/folder IDs. Never commit it
  to public GitHub or send the entire checkpoint.

## Usage (Mac, no login/no scraping)

```bash
cd ~/Downloads/abel-naver-probe
git pull origin feat/naver-readonly-network-probe-20261023
source .venv/bin/activate
python -m unittest discover -s tests -p 'test_naver_priority_p1_p7.py' -v
python -u scripts/naver_priority_p1_p7.py
```

Input is the already-completed owner-local
`~/Library/Application Support/Abel/Wordbooks/checkpoint.json`
and existing
`~/Documents/Abel_Naver_Wordbook/naver_wordbook_verified.json`.

Output is **separate** from the established P1-P4 snapshot:

- `~/Documents/Abel_Naver_Wordbook/naver_wordbook_priority_p1_p7.json`
- `~/Documents/Abel_Naver_Wordbook/naver_wordbook_priority_p1_p7_status.json`

The script checks folder/card counts against the pre-existing verified
snapshot, fails closed if stale extra folder entries are detected, and
never overwrites the original wordbook JSON. No Google Drive upload,
cloud login, API calls, launchd schedule, or public data is produced.

## Acceptance gates before production

1. Synthetic offline tests pass on the Mac.
2. Owner-local `_status.json` shows seven priority counts, reference
   folder count, source limitations and unresolved count.
3. Inspect a sample of P4/P5/P6 for source and reading/sense accuracy.
4. Check whether missing/partial HSK 5 sources require a verified master list.
5. Resolve the 45 unsupported card shapes separately before considering
   priorities definitive.
6. Only then migrate the UI and study-queue routing from P1-P4 to P1-P7.
