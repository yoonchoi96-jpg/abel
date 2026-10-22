# Abel — owner-local Naver wordbook snapshot (experimental)

This collector is a *manual, read-only staging step* in draft PR #6.
It is **not** an official Naver Open API, a production sync service or
an account scraper deployed in the cloud.

## What it does

1. Launches a dedicated Chromium browser profile in the Mac's local
   Application Support directory (outside the previously Drive-synced
   ~/.naver_wordbook/browser_profile).
2. Opens Naver's Chinese personal wordbook UI. Log in manually in this
   dedicated window on the first run.
3. Navigates normal first-party wordbook pages and observes their
   JSON responses; does not replay independent API requests.
4. Requires a complete personal-folder list in ONE UI response. The current
   observed sample contained 19 folder records; if there are multiple
   folder pages the collector FAILS CLOSED instead of omitting folders.
5. Visits each folder and its UI card pages, checking m_total, m_total_pages,
   m_current_page, wordbookId, folder.wordCount, duplicate IDs and page
   completeness. 403/429 and schema drift stop the run.
6. Decodes the JSON-string card.content and normalizes entry.members,
   entry.means and unique folder memberships using naver_wordbook_parser.py.
7. Writes only a **verified, complete** preview and a small status summary.
   It does NOT modify data/naver_wordbook.json or create a schedule.

The normalization retains entry means, part of speech, card IDs, per-folder
membership and P1=4+ folders, P2=3, P3=2, P4=1. It does not assume
entry.mix_pron is confirmed pinyin; unavailable pinyin stays blank.

## Mac usage

Inside the pre-existing ~/Downloads/abel-naver-probe checkout:

    cd ~/Downloads/abel-naver-probe
    git pull origin feat/naver-readonly-network-probe-20261023
    source .venv/bin/activate
    python -m pip install playwright
    python -m playwright install chromium

Run the offline unit tests before account access:

    python -m unittest discover -s tests -p 'test_naver_wordbook_*.py' -v
    python -m unittest discover -s tests -p 'test_naver_network_probe.py' -v

Then run an explicit, user-present snapshot:

    python scripts/naver_wordbook_collect.py

Log in to Naver inside the newly opened Chromium browser. When you see
your Chinese wordbook home, press Enter in the terminal. The tool then
reads all visible wordbooks and pages. Do not run simultaneously with
another scraper using the same profile.

Successful files:

    ~/Documents/Abel_Naver_Wordbook/naver_wordbook_verified.json
    ~/Documents/Abel_Naver_Wordbook/naver_wordbook_status.json

On an incomplete run, an INCOMPLETE error is shown, and verified output
is not replaced. If the UI stops issuing word/list/search requests when
navigated, this staged script must be adapted, not forced to declare success.
It will not silently infer missing pages or treat them as deletions.

## Optional Google Drive publication

Only after the manual snapshot has succeeded, select an **existing,
mounted local Google Drive folder** and run, for example:

    python scripts/naver_wordbook_collect.py --publish-to-drive \
      --drive-dir "/FULL/MAC/PATH/TO/YOUR/Google Drive/Abel_Naver_Wordbook"

The path is a *Mac filesystem path*, NOT a Google Drive URL or file ID.
The tool never sends authentication secrets to Drive, but the verified
wordbook JSON **does contain private saved words, translations, and folder IDs**.
Store only in the user's private Drive, and keep browser profiles outside
Google Drive/iCloud sync folders. Publishing is off by default.

A complete unchanged snapshot is not rewritten locally. If the Drive copy
is missing, explicit publish can still upload the prior verified snapshot.

## Explicitly NOT part of this change

- Automatic 5-minute polling / launchd installation
- Unattended authentication, CAPTCHA bypass, cookie export or token sharing
- Direct calls from an external client to Naver's undocumented endpoints
- Merge into Abel's production importer or modification of its canonical file
- A claim that first live collection works without a Mac login test

## Next acceptance gates

- Offline parser and collection tests pass on the owner Mac.
- A real authenticated run reports COMPLETE and every folder/page count matches.
- Inspect a sample of normalized cards for Chinese, Korean meaning, and
  empty pinyin without silently filling missing fields.
- Re-run unchanged and confirm no duplicate writes.
- Opt in to Drive publication; verify a private Drive copy.
- Only then decide on a limited, low-cost periodic change-detection loop
  within the owner Mac, respecting service access rules.


## Troubleshooting: no verified JSON appears

An incomplete collection intentionally does NOT write
naver_wordbook_verified.json or naver_wordbook_status.json.

The updated collector ALWAYS writes a privacy-safe local attempt file:

    ~/Documents/Abel_Naver_Wordbook/naver_wordbook_attempt.json

It records stage, attempted/current folder NUMBER, completed-folder count,
and sanitized error category/message. It excludes folder IDs, user-saved
Chinese words, meanings, tokens, cookies, authentication headers and URLs.
It does not upload this file to Drive by default.

To determine whether the script was ever started, run these commands
SEPARATELY (avoid using && after unit tests, which might skip collection):

    cd ~/Downloads/abel-naver-probe
    git pull origin feat/naver-readonly-network-probe-20261023
    source .venv/bin/activate
    python -u scripts/naver_wordbook_collect.py

After the collector either completes or exits:

    cat ~/Documents/Abel_Naver_Wordbook/naver_wordbook_attempt.json

Common stages:
- WAITING_FOR_LOGIN: the collector needs the owner to finish login and Enter.
- READING_FOLDER_INDEX: UI folder list was not observed / schema invalid.
- READING_FOLDER_CARDS: a folder's first-party card response was missing or
  a page/count check failed; inspect folder_index and completed_folders.
- VERIFYING_ALL_PAGES: parsing or source identity/count validation failed.
- WRITING_VERIFIED_SNAPSHOT: private filesystem or existing-file issue.
- FINISHED: fully validated run with a verified local snapshot.
- INCOMPLETE: look at error_stage and error_category for the last failed step.

If no attempt file appears, the command did not reach collector.main()
(e.g., unit tests blocked the original && chain, git pull failed, Python
environment missing, import error or wrong checkout). Share the terminal
error text, but NEVER share Naver cookies, login tokens or browser profiles.


## Verified local diagnostic: meta.status=1 on the folder endpoint

On 2026-10-23 KST the owner ran the browser collector and observed:

    READING_FOLDER_INDEX
    INCOMPLETE: Unrecognized Naver application status code: 1

The request was HTTP 200. Earlier, the safe schema-only UI probe showed
that this folder endpoint returns a pagination envelope with fields
m_items, m_total, m_page and m_totalPage.

The collector has been updated to conditionally accept integer
meta.status=1 ONLY when that response also has a structurally valid
folder- or card-page envelope. It still rejects other unexpected codes,
error-shaped status=1 payloads, missing fields and incomplete pagination.
This is grounded in the user's observed UI response, not an official
documented Naver success-code contract.

On the Mac, update the branch and run:

    cd ~/Downloads/abel-naver-probe
    git pull origin feat/naver-readonly-network-probe-20261023
    source .venv/bin/activate
    python -m unittest discover -s tests -p 'test_naver_wordbook_*.py' -v
    python -u scripts/naver_wordbook_collect.py

If the collector fails again, share ONLY the sanitized
naver_wordbook_attempt.json or the terminal error text, not profile,
cookies, private saved word contents or request URLs.
