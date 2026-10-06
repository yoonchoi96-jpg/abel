# Hanping → Abel ingestion

Hanping is the user-facing vocabulary inbox. Abel is the canonical normalizer.

## Current safe boundary

`hanping_vocab_import.py` accepts a vocabulary export/file and normalizes it into:

- hanzi
- simplified
- traditional
- pinyin
- starred
- tags
- note
- record_hash

The importer deliberately does not handle Hanping login, OTPs, cookies, or browser sessions.

## Current Hanping flow

1. In Hanping iPhone: Settings → Backup/Restore → sign in → **Back up to Cloud**.
2. Open **My Vocabulary** in a normal browser and sign in with the same Hanping account.
3. Once an actual vocabulary export/file is available, feed that file to this importer.
4. Abel merges duplicate headwords and preserves the union of tags plus starred/note state.
5. Dictionary/HSK enrichment happens downstream.

Hanping's official documentation says Cloud Backup stores starred words, custom tags, notes and history, and uploads only after the user explicitly taps Back up to Cloud. The My Vocabulary page decrypts the backup in the browser.

Canonical HSK 3.0 data remains Abel-owned; Hanping tags are user metadata/reference signals only.
