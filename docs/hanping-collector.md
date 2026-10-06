# Hanping to Abel Collector

Hanping Cloud Backup is the source boundary. Hanping documents that Cloud Backup
contains starred words, custom tags, notes and search history, and that backups
are encrypted before storage. Upload happens only when the user taps Back up to Cloud.

The public My Vocabulary web app is the inspection surface. It decrypts data in
the browser, so Abel should not implement Hanping cryptography.

V1 workflow:
1. Study in Hanping.
2. Star, tag, or annotate vocabulary.
3. Tap Back up to Cloud.
4. On Mac, open My Vocabulary with a persistent local Playwright profile.
5. Sign in interactively when needed.
6. Inspect where decrypted vocabulary lives: JS state, IndexedDB, network data,
   or DOM as a last resort.
7. Implement extractor only after that inspection.
8. Normalize into Abel and upsert by stable hash.
9. Enrich with Abel-owned HSK 3.0, TOCFL, and dictionary layers.
10. Export downstream to Obsidian.

Security:
- Browser profile: ~/.abel/hanping-browser
- Inspection output: ~/.abel/hanping-inspect
- Never commit cookies, storage-state JSON, OTPs, passwords, auth headers,
  browser profiles, or raw Hanping backups.
- Inspection output can contain private vocabulary.

Install:
python -m pip install playwright
python -m playwright install chromium

Run:
python scripts/hanping_inspect.py

The inspector is deliberately not a production collector yet. Its purpose is to
identify the most stable plaintext data surface exposed by the official web app.
