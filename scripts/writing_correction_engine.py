#!/usr/bin/env python3
"""Abel Chinese writing-correction contract and prompt engine.

The engine is model-agnostic: deterministic normalization/cache keys are handled
locally, while the actual linguistic judgment is delegated to the configured LLM.
It preserves four layers: original -> minimal correction -> natural version ->
advanced/HSK6+ version.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

ENGINE = "Abel Chinese Writing Correction Engine"
VERSION = "1.0.0"
PROMPT_VERSION = "abel-writing-v1"

VALID_LEVELS = {"HSK5", "HSK6", "HSK7-9", "GENERAL"}
VALID_REGISTERS = {"neutral", "formal", "colloquial", "academic", "news", "business", "literary"}

OUTPUT_CONTRACT = {
    "schema_version": "abel.writing.v1",
    "engine": ENGINE,
    "version": VERSION,
    "original": "",
    "language": "zh-CN",
    "overall": {
        "status": "correct|revise",
        "summary_ko": "",
        "severity": "none|minor|major"
    },
    "versions": {
        "minimal_correction": "",
        "natural_version": "",
        "advanced_version": ""
    },
    "issues": [
        {
            "type": "grammar|word_choice|collocation|word_order|register|naturalness|logic|punctuation",
            "severity": "minor|major",
            "span": "",
            "original": "",
            "correction": "",
            "explanation_ko": "",
            "rule": ""
        }
    ],
    "vocabulary_usage": [
        {
            "word": "",
            "status": "correct|awkward|incorrect",
            "note_ko": "",
            "word_id": None
        }
    ],
    "hsk": {
        "target_level": "HSK6",
        "writing_quality": "below|meets|strong|advanced",
        "score": 0,
        "score_scale": "0-100",
        "rationale_ko": ""
    },
    "better_expressions": [],
    "next_practice": [],
    "confidence": "high|medium|low",
    "validation_notes": []
}


def normalize_text(text: str) -> str:
    text = str(text or "").strip()
    text = re.sub(r"[ \t\r\n]+", " ", text)
    return text


def correction_cache_key(
    text: str,
    *,
    target_level: str = "HSK6",
    register: str = "neutral",
    prompt_version: str = PROMPT_VERSION,
) -> str:
    payload = {
        "text": normalize_text(text),
        "target_level": target_level,
        "register": register,
        "prompt_version": prompt_version,
        "engine_version": VERSION,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_writing_prompt(
    text: str,
    *,
    target_level: str = "HSK6",
    register: str = "neutral",
    context: str = "",
    known_words: list[dict[str, Any]] | None = None,
) -> str:
    text = normalize_text(text)
    target_level = target_level if target_level in VALID_LEVELS else "HSK6"
    register = register if register in VALID_REGISTERS else "neutral"
    known_words = known_words or []

    known_json = json.dumps(known_words[:100], ensure_ascii=False)
    context = normalize_text(context)[:10000]

    return f"""You are Abel Chinese Writing Correction Engine.
Target learner: advanced Korean learner, HSK6 -> HSK 3.0 7-9.
Target level: {target_level}
Target register: {register}
Prompt version: {PROMPT_VERSION}

INPUT
Chinese text:
{text}

Context:
{context or "(none)"}

Known Abel vocabulary metadata:
{known_json}

CORE RULES
1. Do not rewrite a correct sentence merely because another phrasing is possible.
2. Separate grammar errors, incorrect word choice, bad collocation, word order,
   register mismatch, logic problems, and merely unnatural phrasing.
3. Preserve the learner's intended meaning unless it is genuinely unclear.
4. Produce FOUR layers:
   original (verbatim), minimal correction, natural version, advanced/target-level version.
5. Minimal correction must change only what is necessary for correctness.
6. Natural version should sound like contemporary standard Mandarin.
7. Advanced version may use more sophisticated syntax/vocabulary, but must remain natural
   and must not inflate difficulty artificially.
8. For every issue, quote only the relevant short span and explain it in Korean.
9. Never invent a rule, collocation, frequency statistic, HSK test-frequency claim,
   etymology, or citation.
10. If the sentence is already correct, say so explicitly and keep minimal_correction
    identical to the original.
11. Check every supplied known-word item for actual usage in context. Do not assume that
    because a word belongs to a wordbook it is correctly used.
12. HSK score is descriptive, not a claim about an official exam score.
13. Return JSON only. No Markdown fences and no prose outside JSON.

OUTPUT JSON
{json.dumps(OUTPUT_CONTRACT, ensure_ascii=False, indent=2)}

VALIDATION
- original must equal the supplied Chinese text after only outer whitespace normalization.
- versions must all be present.
- issues must be an array.
- vocabulary_usage must be an array.
- hsk.score must be 0-100.
- Do not silently omit a detected major error.
"""


def validate_correction(result: dict[str, Any], original: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(result, dict):
        return ["result must be a JSON object."]

    required = {"schema_version", "engine", "version", "original", "overall",
                "versions", "issues", "vocabulary_usage", "hsk", "confidence"}
    missing = sorted(required - set(result))
    if missing:
        errors.append("Missing fields: " + ", ".join(missing))

    if result.get("schema_version") != "abel.writing.v1":
        errors.append("Invalid schema_version.")
    if result.get("engine") != ENGINE:
        errors.append("Invalid engine.")
    if normalize_text(result.get("original", "")) != normalize_text(original):
        errors.append("original does not match the supplied input.")

    versions = result.get("versions")
    if not isinstance(versions, dict):
        errors.append("versions must be an object.")
    else:
        for key in ("minimal_correction", "natural_version", "advanced_version"):
            if not isinstance(versions.get(key), str) or not versions[key].strip():
                errors.append(f"versions.{key} must be a non-empty string.")

    if not isinstance(result.get("issues"), list):
        errors.append("issues must be an array.")
    if not isinstance(result.get("vocabulary_usage"), list):
        errors.append("vocabulary_usage must be an array.")

    hsk = result.get("hsk")
    if not isinstance(hsk, dict):
        errors.append("hsk must be an object.")
    else:
        score = hsk.get("score")
        if not isinstance(score, (int, float)) or isinstance(score, bool) or not 0 <= score <= 100:
            errors.append("hsk.score must be between 0 and 100.")

    if result.get("confidence") not in {"high", "medium", "low"}:
        errors.append("confidence must be high, medium, or low.")

    return errors


def make_correction_envelope(
    original: str,
    *,
    target_level: str = "HSK6",
    register: str = "neutral",
    context: str = "",
    known_words: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    normalized = normalize_text(original)
    if not normalized:
        raise ValueError("Chinese writing text is required.")
    if len(normalized) > 20000:
        raise ValueError("Chinese writing text exceeds 20,000 characters.")

    return {
        "status": "ready_for_llm",
        "engine": ENGINE,
        "version": VERSION,
        "prompt_version": PROMPT_VERSION,
        "cache_key": correction_cache_key(
            normalized,
            target_level=target_level,
            register=register,
        ),
        "input": normalized,
        "target_level": target_level if target_level in VALID_LEVELS else "HSK6",
        "register": register if register in VALID_REGISTERS else "neutral",
        "context": normalize_text(context),
        "known_word_count": len(known_words or []),
        "prompt": build_writing_prompt(
            normalized,
            target_level=target_level,
            register=register,
            context=context,
            known_words=known_words,
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
