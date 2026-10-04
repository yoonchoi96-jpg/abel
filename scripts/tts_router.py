#!/usr/bin/env python3
"""Central TTS routing for Abel.

Routing is deliberately independent of learning content.  The current production
route is Gemini TTS for Chinese lesson audio; provider/model/voice can be changed
centrally without changing callers.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class TTSRoute:
    language: str
    provider: str
    model: str
    voice: str
    style: str


_DEFAULT_STYLE = (
    "Natural, clear Standard Mandarin for HSK listening practice. "
    "Use restrained, realistic spoken prosody. Preserve the transcript exactly."
)

_STYLE_BY_MODE = {
    "conversational_dialogue": (
        "Natural, relaxed Standard Mandarin conversation between educated adults. "
        "Use realistic conversational prosody without exaggerated acting. Preserve the transcript exactly."
    ),
    "interview": (
        "Natural, clear Standard Mandarin interview delivery. "
        "Sound spontaneous and articulate, with restrained professional prosody. Preserve the transcript exactly."
    ),
    "news_report": (
        "Clear professional Standard Mandarin news delivery. "
        "Controlled broadcast prosody, information-dense but natural. Preserve the transcript exactly."
    ),
    "announcement": (
        "Clear official Standard Mandarin announcement. "
        "Concise, orderly, calm and highly intelligible. Preserve the transcript exactly."
    ),
    "lecture_explanation": (
        "Natural educated Standard Mandarin explanation. "
        "Logical spoken phrasing, calm and articulate, not an essay reading. Preserve the transcript exactly."
    ),
    "narrative_story": (
        "Natural Standard Mandarin storytelling. "
        "Expressive but restrained, with clear temporal and narrative phrasing. Preserve the transcript exactly."
    ),
    "formal_informational": (
        "Calm professional Standard Mandarin informational delivery. "
        "Relatively formal but naturally spoken. Preserve the transcript exactly."
    ),
    "casual_explanation": (
        "Natural relaxed Standard Mandarin explanation by an educated adult. "
        "Conversational but not slangy or theatrical. Preserve the transcript exactly."
    ),
}


def resolve_tts_route(
    language: str = "zh-CN",
    *,
    delivery_mode: str = "casual_explanation",
    speaker_mode: str = "single",
) -> TTSRoute:
    language = (language or "zh-CN").strip()
    delivery_mode = (delivery_mode or "casual_explanation").strip()
    speaker_mode = (speaker_mode or "single").strip()

    if language != "zh-CN":
        raise ValueError(
            f"No production TTS route is active for {language!r}. "
            "Only zh-CN is active in the current learning period."
        )

    if delivery_mode not in _STYLE_BY_MODE:
        raise ValueError(f"Unsupported delivery_mode: {delivery_mode!r}")

    if speaker_mode not in {"single", "dual"}:
        raise ValueError("speaker_mode must be 'single' or 'dual'.")

    # Dual-speaker Gemini routing is reserved for the multi-speaker renderer.
    # Keep the single-speaker renderer fail-closed instead of silently producing
    # the wrong voice configuration.
    if speaker_mode == "dual":
        raise ValueError(
            "dual speaker routing requires the Gemini multi-speaker renderer; "
            "the single-speaker production path will not silently downgrade."
        )

    return TTSRoute(
        language=language,
        provider="gemini",
        model=os.getenv("GEMINI_TTS_MODEL", "gemini-3.8-flash-tts"),
        voice=os.getenv("GEMINI_TTS_VOICE", "Kore"),
        style=os.getenv("GEMINI_TTS_STYLE", _STYLE_BY_MODE[delivery_mode]),
    )
