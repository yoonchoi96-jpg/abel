# Naver Chinese personal wordbook API observation — 2026-10-23

**State: OBSERVED, NOT INTEGRATED.** First-party Naver browser traffic has internal JSON endpoints. These are **not an official public API**. No direct request replay or unattended sync was verified.

## Evidence

Source: owner's metadata-only naver_api_probe.json recorded at 2026-10-22T18:01:14.852906Z (03:01:14 KST, 2026-10-23). Fourteen endpoint groups observed; every captured status code is 200. No authentication credentials, folder names/IDs, word text, query values, or JSON response values were exported.

| Function | First-party GET endpoint (learn.dict.naver.com) | Observed result |
| --- | --- | --- |
| Wordbook folders | /gateway-api/zhkodict/mywordbook/wordbook/list.dict | one response contained 19 items; pagination field names m_total, m_page, m_totalPage |
| Wordbook metadata | /gateway-api/zhkodict/mywordbook/wordbook/detail | fields include id, name, wordCount, updateTimestamp; 8 observations with wbId |
| Wordbook cards | /gateway-api/zhkodict/mywordbook/word/list/search | one response contained 20 items; pagination field names m_total, m_current_page, m_total_pages |
| Aggregate word counts | /gateway-api/zhkodict/mywordbook/word/count.dict | readCount, unReadCount, recentCount |

Response envelope: meta object with status/message; data object with service-specific fields.

**Important limits:** The array lengths 19 and 20 are per-observation sample sizes, not verified grand totals. The diagnostic truncated schema depth before the 14 individual word-card field names; therefore word/pinyin/meaning mappings remain unverified. The value of m_total, total pages, and all user-specific IDs/values were intentionally excluded.

## Next phase

1. An expanded-depth version of the same owner-local, metadata-only diagnostic now shows the *field names and types* of a sample word-card object, still omitting all values.
2. Run the diagnostic again after opening at least one wordbook folder to obtain those field names.
3. Validate page counts and folder coverage against the Naver UI. Only then decide whether an owner-local, read-only collector is appropriate under applicable service access rules.
4. Never push browser profiles, cookies, token data, HAR files, or Naver credentials into GitHub, Google Drive, or logs.
5. Never treat failed or incomplete reads as word deletions. No direct-call sync or polling schedule is activated by this report.

## Local rerun

In a Mac checkout of the feature branch:

    git pull origin feat/naver-readonly-network-probe-20261023
    python scripts/naver_network_probe.py --duration 90

Log into Naver if prompted, click several separate Chinese wordbook folders and a page of cards, then share only the generated naver_api_probe.json.

The production Abel import boundary, data/naver_wordbook.json, remains unchanged.


## Second diagnostic: 03:23:22 KST

Owner supplied a new report (captured_at 2026-10-22T18:23:22.854235Z, 7,872 bytes).
This report is distinct from the 03:01 report. It contains four groups:
category/list, wordbook/list.dict, user/message.dict and word/count.dict.
No word/list/search event was observed. The expanded skeleton correctly
shows all 20 folder-item field names and types from 19 items, but cannot
show word-card fields without a word-card response.

The probe now automatically clicks a visible personal wordbook link (read-only
UI navigation) after login, with a manual click fallback and a warning if no
word/list/search endpoint was observed. This changes only the experimental
probe, not the production sync architecture.

To get card field types, update this branch then run the local probe again.
No passwords, cookies, folder ID values, words or meanings belong in the
diagnostic report.
