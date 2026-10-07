# Hanping → Abel ingestion

Hanping is the user-facing vocabulary inbox. Abel is the canonical normalizer.

## Supported ingestion boundary

`hanping_vocab_import.py` accepts a vocabulary export/file and normalizes it into:

- hanzi / simplified
- traditional
- pinyin
- starred
- tags
- note
- deterministic `record_hash`

It supports JSON, CSV, TSV and plain text. Duplicate headwords are merged; starred state is OR-merged, tags are unioned, and non-empty note/traditional/pinyin values are retained.

The importer deliberately does **not** handle Hanping login, OTPs, cookies, browser sessions, or private cloud decryption.

## Recommended iPhone flow

1. Study in Hanping.
2. Star words and add tags/notes as needed.
3. In Hanping: **Settings → Backup/Restore → Cloud → Back up to Cloud**.
4. For a file-based ingestion path, use Hanping's official **Import/Export Vocab File** feature and export the vocabulary to a text file.
5. Put the exported file into the local Abel ingestion path and run the importer.
6. Abel normalizes and upserts the vocabulary.
7. Dictionary / HSK 3.0 / TOCFL enrichment happens downstream.
8. Obsidian remains a downstream destination.

Hanping's official documentation says Cloud Backup contains starred words, custom tags, notes and search history, and that nothing is uploaded until the user explicitly taps **Back up to Cloud**. Hanping also documents Import/Export Vocab File as a separate one-off in-app purchase feature.

## Data ownership

- **Hanping:** user vocabulary signal — starred state, tags, notes, history.
- **Abel:** canonical vocabulary identity and enrichment, including the user's existing HSK 3.0 datasets.
- **Obsidian:** downstream knowledge/learning presentation.

Hanping HSK/TOCFL labels must not replace Abel's canonical HSK 3.0 datasets.

## Operational rule

Never commit exported vocabulary, cloud backups, cookies, session state, passwords, OTPs, auth headers, or other private account material to the repository.
