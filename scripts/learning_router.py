#!/usr/bin/env python3
"""Canonical learning-content routing for Abel."""
from __future__ import annotations
import re
from dataclasses import dataclass

LANGUAGE_LABELS = {
    "zh": "Chinese", "zh-cn": "Chinese", "zh_cn": "Chinese", "chinese": "Chinese",
    "es": "Spanish", "es-es": "Spanish", "spanish": "Spanish",
    "fr": "French", "fr-fr": "French", "french": "French",
}
SKILL_LABELS = {
    "reading": "Reading", "read": "Reading",
    "listening": "Listening", "listen": "Listening",
    "writing": "Writing", "write": "Writing",
    "speaking": "Speaking", "speak": "Speaking",
    "vocabulary": "Vocabulary", "vocab": "Vocabulary",
    "grammar": "Grammar", "culture": "Culture",
}
LEVEL_SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,39}$")

@dataclass(frozen=True)
class LearningRoute:
    language_code: str
    language: str
    skill: str
    level: str
    parts: tuple[str, ...]

def _key(value: str) -> str:
    return re.sub(r"\s+", "-", (value or "").strip().lower())

def normalize_language(value: str) -> tuple[str, str]:
    key = _key(value)
    if key not in LANGUAGE_LABELS:
        raise ValueError(f"Unsupported learning language: {value!r}")
    label = LANGUAGE_LABELS[key]
    code = {"Chinese": "zh-CN", "Spanish": "es", "French": "fr"}[label]
    return code, label

def normalize_skill(value: str) -> str:
    key = _key(value)
    if key not in SKILL_LABELS:
        raise ValueError(f"Unsupported learning skill: {value!r}")
    return SKILL_LABELS[key]

def normalize_level(value: str, default: str = "General") -> str:
    level = (value or "").strip() or default
    if not LEVEL_SAFE.fullmatch(level):
        raise ValueError(f"Unsafe learning level/path segment: {value!r}")
    return level

def resolve_learning_route(*, language: str, skill: str, level: str = "") -> LearningRoute:
    code, language_label = normalize_language(language)
    skill_label = normalize_skill(skill)
    level_label = normalize_level(level)
    return LearningRoute(code, language_label, skill_label, level_label,
                         (language_label, skill_label, level_label))
