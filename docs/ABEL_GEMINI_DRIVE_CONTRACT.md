# Abel Drive Contract v1

Abel/
├── KNOWLEDGE/
│   ├── Abel_Chinese_Education_Engine.md
│   ├── Abel_Education_Output_Schema.json
│   └── Chinese_Education_Reference.md
├── INBOX/
│   └── batch-YYYYMMDD-HHMMSS.json
├── OUTBOX/
│   └── batch-YYYYMMDD-HHMMSS.educated.json
└── ARCHIVE/
    └── imported completed batches

## Routing
1. Abel writes newly classified words to INBOX.
2. Gemini Gem reads the requested INBOX batch.
3. Gemini returns exactly the output contract.
4. The completed JSON is saved to OUTBOX using the same batch_id.
5. Abel imports OUTBOX, validates word_id uniqueness, merges education data, then archives the processed file.
6. Abel never needs a Gemini API key or Google API key.

## Idempotency
- batch_id is the stable unit of work.
- word_id is the stable identity of a word.
- Abel must not duplicate an education record for the same word_id.
- Reprocessing the same batch must be safe.
