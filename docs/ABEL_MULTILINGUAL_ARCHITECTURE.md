# Abel Multilingual Learning Architecture

## Goal

Abel is a single multilingual learning engine. Chinese is the active language
today; French, English, Spanish, Japanese, and German can be activated later
without restructuring the engine.

## Boundaries

### Shared engine

The existing deterministic learning/session/review/scoring/QA/TTS components
are shared. They must not be copied into per-language directories.

### Language boundary

Language-specific content, curriculum metadata, level systems, prompts, and
provider settings live under a locale boundary.

| Locale | Language | Status | Scale |
|---|---|---|---|
| zh-CN | Chinese | active | HSK3.0 |
| fr-FR | French | planned | CEFR |
| en-US | English | planned | CEFR |
| es-ES | Spanish | planned | CEFR |
| ja-JP | Japanese | planned | JLPT |
| de-DE | German | planned | CEFR |

### Asset boundary

Audio and other generated artifacts are separated from canonical learning
content. TTS provider/model/voice is metadata, not a separate learning engine.

## Compatibility rule

This migration is additive. Existing Chinese scripts, workflows, HSK data, and
Drive handoff paths remain intact. No existing path is moved until its runtime
consumer has been migrated and regression-tested.

## Activation rule

Activating a future language means enabling its locale configuration, adding
language-specific content and curriculum metadata, and reusing the common
learning engines. It must not require copying scoring, TTS, question-generation,
review, or learning-history code.

## Drive model

Drive should mirror the conceptual boundary:

Abel Learning/
- languages/<locale>/
- assets/audio/<locale>/
- assets/images/
- assets/documents/
- system/

Google Drive remains a data/artifact handoff layer. Abel remains the source of
truth for durable learning state.
