# Abel

Abel is the Naver Dictionary personal wordbook sync system.

## Architecture

Naver Dictionary authenticated browser session -> Playwright on the user's Mac -> local raw snapshots + SQLite -> data/naver_wordbook.json -> GitHub Actions commit.

GitHub-hosted runners are intentionally not used for the authenticated Naver browser session. A self-hosted Mac runner keeps the login session local.

## One-time setup

1. Clone this repository on the Mac.
2. Install Python 3.11 and Playwright.
3. Run the bootstrap command.
4. Log in to Naver and make sure the personal wordbook is visible.
5. Press Enter in the terminal.
6. Run probe mode.
7. Register the Mac as a GitHub Actions self-hosted runner with labels self-hosted, macOS, naver-wordbook.

Never commit the browser profile. It contains authenticated session data.

## Commands

    python scripts/naver_wordbook_sync.py --bootstrap
    python scripts/naver_wordbook_sync.py --probe
    python scripts/naver_wordbook_sync.py --sync
