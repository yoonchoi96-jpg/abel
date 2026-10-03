#!/usr/bin/env python3
"""Language-agnostic writing correction envelope for Abel."""
from __future__ import annotations
import hashlib, json, re
from datetime import datetime, timezone
from typing import Any

ENGINE = "Abel Multilingual Writing Correction Engine"
VERSION = "1.0.0"
PROMPT_VERSION = "abel-multilingual-writing-v1"
LANGUAGES = {
    "zh-CN": "Chinese (Simplified Mandarin)",
    "fr-FR": "French",
    "es-ES": "Spanish",
    "en-US": "English",
    "ja-JP": "Japanese",
    "de-DE": "German",
}
REGISTERS = {"neutral","formal","colloquial","academic","news","business","literary"}

def normalize_text(text: str) -> str:
    return re.sub(r"[ \t\r\n]+", " ", str(text or "").strip())

def cache_key(text: str, language: str, target_level: str, register: str) -> str:
    payload = {
        "text": normalize_text(text), "language": language,
        "target_level": target_level, "register": register,
        "prompt_version": PROMPT_VERSION, "engine_version": VERSION,
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

def build_prompt(
    text: str, *, language: str, target_level: str = "advanced",
    register: str = "neutral", context: str = "", known_words: list[dict[str, Any]] | None = None
) -> str:
    language_name = LANGUAGES.get(language, language)
    known = json.dumps((known_words or [])[:100], ensure_ascii=False)
    schema = {
        "schema_version": "abel.multilingual.writing.v1",
        "engine": ENGINE, "version": VERSION, "prompt_version": PROMPT_VERSION,
        "language": language, "original": "",
        "overall": {"status": "correct|revise", "summary_ko": "", "severity": "none|minor|major"},
        "versions": {
            "minimal_correction": "", "natural_version": "", "advanced_version": ""
        },
        "issues": [{
            "type": "grammar|word_choice|collocation|word_order|register|naturalness|logic|punctuation",
            "severity": "minor|major", "span": "", "original": "", "correction": "",
            "explanation_ko": "", "rule": ""
        }],
        "vocabulary_usage": [{
            "word": "", "status": "correct|awkward|incorrect", "note_ko": "", "word_id": None
        }],
        "assessment": {
            "target_level": target_level, "score": 0, "score_scale": "0-100",
            "rationale_ko": ""
        },
        "better_expressions": [], "next_practice": [],
        "confidence": "high|medium|low", "validation_notes": []
    }
    return f"""You are Abel Multilingual Writing Correction Engine.
Language: {language_name} ({language})
Target level: {target_level}
Target register: {register}
Context: {normalize_text(context)[:10000] or "(none)"}
Known Abel vocabulary metadata: {known}

Correct the learner's writing without unnecessary rewriting.
Preserve intended meaning. Return four layers:
1) original verbatim
2) minimal correction — only necessary correctness fixes
3) natural version — contemporary native usage
4) advanced version — appropriate to the target level, without artificial difficulty

Classify issues as grammar, word_choice, collocation, word_order, register,
naturalness, logic, or punctuation. Explain issues in Korean.
Distinguish errors from stylistic alternatives. Check supplied vocabulary in context.
Do not invent rules, frequency claims, citations, etymology, or history.
If the text is already correct, say so and keep minimal_correction equal to original.
The score is descriptive, not an official exam score.
Return JSON only, matching this contract exactly:
{json.dumps(schema, ensure_ascii=False, indent=2)}
"""

def make_envelope(text: str, *, language: str, target_level: str = "advanced",
                  register: str = "neutral", context: str = "",
                  known_words: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    normalized = normalize_text(text)
    if not normalized:
        raise ValueError("Writing text is required.")
    if language not in LANGUAGES:
        raise ValueError("Unsupported language. Supported: " + ", ".join(LANGUAGES))
    if register not in REGISTERS:
        register = "neutral"
    return {
        "status": "ready_for_llm", "engine": ENGINE, "version": VERSION,
        "prompt_version": PROMPT_VERSION, "language": language,
        "target_level": target_level, "register": register,
        "cache_key": cache_key(normalized, language, target_level, register),
        "input": normalized,
        "prompt": build_prompt(
            normalized, language=language, target_level=target_level,
            register=register, context=context, known_words=known_words
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

def validate_result(result: dict[str, Any], original: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(result, dict):
        return ["result must be a JSON object."]
    for key in ("schema_version","engine","version","language","original","overall",
                "versions","issues","vocabulary_usage","assessment","confidence"):
        if key not in result:
            errors.append("Missing field: " + key)
    if result.get("schema_version") != "abel.multilingual.writing.v1":
        errors.append("Invalid schema_version.")
    if result.get("engine") != ENGINE:
        errors.append("Invalid engine.")
    if normalize_text(result.get("original","")) != normalize_text(original):
        errors.append("original does not match supplied input.")
    versions = result.get("versions")
    if not isinstance(versions, dict):
        errors.append("versions must be an object.")
    else:
        for key in ("minimal_correction","natural_version","advanced_version"):
            if not isinstance(versions.get(key), str) or not versions[key].strip():
                errors.append("versions." + key + " must be non-empty.")
    if not isinstance(result.get("issues"), list):
        errors.append("issues must be an array.")
    if not isinstance(result.get("vocabulary_usage"), list):
        errors.append("vocabulary_usage must be an array.")
    assessment = result.get("assessment")
    if not isinstance(assessment, dict):
        errors.append("assessment must be an object.")
    elif not isinstance(assessment.get("score"), (int,float)) or isinstance(assessment.get("score"), bool) or not 0 <= assessment["score"] <= 100:
        errors.append("assessment.score must be between 0 and 100.")
    if result.get("confidence") not in {"high","medium","low"}:
        errors.append("confidence must be high, medium, or low.")
    return errors
