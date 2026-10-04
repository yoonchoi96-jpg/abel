# Abel language data boundary

Each language gets a stable locale directory. Language directories contain
learning data and language-specific configuration, not duplicated algorithms.

Current active language:
- zh-CN

Reserved future languages:
- fr-FR
- en-US
- es-ES
- ja-JP
- de-DE

Shared algorithms stay under the repository's common engine/scripts layer.
When a new language is activated, add its data/configuration without copying
the scoring, QA, question-generation, review, learning-history, or TTS engines.
