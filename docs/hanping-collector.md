# Hanping → Abel Collector

## Scope

Hanping is the vocabulary capture UI. Abel owns normalization, canonical identity, enrichment and downstream export.

The supported boundary is **file-based Hanping vocabulary ingestion**. The collector does not automate Hanping account authentication or private cloud decryption.

## V1 flow

1. Study in Hanping.
2. Star words and use custom tags/notes.
3. Optionally use Hanping Cloud Backup for an off-device copy.
4. Export vocabulary with Hanping's official **Import/Export Vocab File** feature.
5. Feed the exported text file to `scripts/hanping_vocab_import.py`.
6. Abel normalizes, deduplicates and produces deterministic hashes.
7. Existing Abel HSK 3.0 / TOCFL / dictionary layers enrich the canonical entry.
8. Obsidian consumes the normalized downstream representation.

## Security boundary

Never put Hanping passwords, OTPs, cookies, browser profiles, auth headers, cloud backups or raw private vocabulary exports into GitHub.

The importer contains no authentication/session automation and does not implement Hanping's cloud encryption.

## Current blocker

Hanping's public My Vocabulary page is a browser-side viewing surface for cloud-backed vocabulary. There is no documented public API/export endpoint in the official documentation that Abel can safely treat as a stable machine interface.

Therefore the production collector is deliberately **file-based** until a supported machine-readable interface is available.
