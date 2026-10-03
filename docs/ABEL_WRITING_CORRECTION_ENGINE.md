# Abel Chinese Writing Correction Engine

## Purpose

Abel now supports a model-agnostic Chinese writing-correction pipeline for an advanced Korean learner.

The pipeline separates deterministic infrastructure from linguistic judgment:

1. Normalize input.
2. Generate a stable cache key from text + target level + register + engine/prompt version.
3. Build a strict JSON-only LLM prompt.
4. Require four output layers: original, minimal correction, natural version, advanced/target-level version.
5. Validate the returned JSON contract.
6. Persist correction history locally in SQLite.
7. Aggregate recurring error types and problematic vocabulary.

## MCP tools

### prepare_chinese_writing_correction

Inputs: text, target_level, register, optional context, optional known_words_json.

Returns a model-ready prompt and a SHA-256 cache key.

### validate_chinese_writing_correction

Validates model output against the Abel writing schema and verifies that the original text was not silently changed.

## Four correction layers

Abel must not turn every correct sentence into a stylistic rewrite.

- Minimal correction: only changes what is necessary for correctness.
- Natural version: contemporary standard Mandarin.
- Advanced version: stronger HSK6+/7–9 expression without artificial difficulty inflation.

## Personal error history

scripts/writing_history.py stores local learning history in data/abel_learning.db. The database is ignored by Git.

It stores correction records, issue types/severity, problematic vocabulary usage, engine/prompt versions, and HSK writing-score metadata.

Repeated cache keys are idempotent, so the same correction is not stored repeatedly.

## API efficiency

The cache key includes normalized text, target level, register, engine version, and prompt version. Unchanged requests can therefore be reused by the calling layer without another model call.

## Relationship to HSK evaluation

The existing hsk_evaluation_engine.py remains the deterministic QA engine for generated HSK exam content. The new writing engine is for learner-produced free writing. They are complementary.

The writing score is descriptive and is not an official HSK score.
