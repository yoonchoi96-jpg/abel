#!/usr/bin/env python3
"""Gemini TTS renderer for Abel.

Gemini 3.8 Flash TTS returns WAV audio for unary requests.
The renderer supports both single-speaker and native two-speaker dialogue.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from google import genai
from google.genai import types

try:
    from tts_router import resolve_tts_route
except ModuleNotFoundError:
    from scripts.tts_router import resolve_tts_route

SAMPLE_RATE = 24000

_SPEAKER_CONFIG = {
    "男": {"speaker": "Male", "voice": "Puck"},
    "女": {"speaker": "Female", "voice": "Kore"},
}
_TURN_RE = re.compile(r"^\\s*(男|女)\\s*[:：]\\s*(.+?)\\s*$")


def wav_to_mp3(wav_path: str | Path, mp3_path: str | Path, bitrate: str = "128k") -> Path:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is required to convert Gemini WAV to MP3.")
    source = Path(wav_path)
    target = Path(mp3_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(source),
        "-codec:a", "libmp3lame", "-b:a", bitrate, "-ar", str(SAMPLE_RATE), "-ac", "1",
        str(target),
    ], check=True)
    if not target.exists() or target.stat().st_size == 0:
        raise RuntimeError("ffmpeg produced no MP3 output.")
    return target


def _parse_dual_speaker_script(script: str) -> list[tuple[str, str]]:
    turns: list[tuple[str, str]] = []
    for line in script.splitlines():
        line = line.strip()
        if not line:
            continue
        match = _TURN_RE.match(line)
        if not match:
            raise ValueError(
                "Dual-speaker TTS requires every dialogue turn to start with "
                "'男：' or '女：'."
            )
        speaker, text = match.groups()
        if text.strip():
            turns.append((_SPEAKER_CONFIG[speaker]["speaker"], text.strip()))

    if not turns:
        raise ValueError("Dual-speaker TTS script contains no dialogue turns.")

    speakers = {speaker for speaker, _ in turns}
    if speakers != {"Male", "Female"}:
        raise ValueError("Dual-speaker TTS requires both 男 and 女 turns.")

    return turns


def _render_single(
    client: genai.Client,
    script: str,
    *,
    model_name: str,
    voice_name: str,
    style_text: str,
) -> bytes:
    response = client.models.generate_content(
        model=model_name,
        contents=[types.Content(
            role="user",
            parts=[types.Part.from_text(text=script)],
        )],
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name)
                )
            ),
        ),
    )
    return _audio_bytes(response)


def _render_dual(
    client: genai.Client,
    turns: list[tuple[str, str]],
    *,
    model_name: str,
    style_text: str,
) -> bytes:
    parts = [
        {
            "text": text,
            "speech_metadata": {
                "speaker": speaker,
                "style": style_text,
            },
        }
        for speaker, text in turns
    ]

    response = client.models.generate_content(
        model=model_name,
        contents=[{"role": "user", "parts": parts}],
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config={
                "multi_speaker_voice_config": {
                    "speaker_voice_configs": [
                        {
                            "speaker": "Male",
                            "voice_config": {
                                "prebuilt_voice_config": {"voice_name": "Puck"}
                            },
                        },
                        {
                            "speaker": "Female",
                            "voice_config": {
                                "prebuilt_voice_config": {"voice_name": "Kore"}
                            },
                        },
                    ]
                }
            },
        ),
    )
    return _audio_bytes(response)


def _audio_bytes(response) -> bytes:
    try:
        data = response.candidates[0].content.parts[0].inline_data.data
    except (AttributeError, IndexError, TypeError) as exc:
        raise RuntimeError("Gemini TTS response did not contain audio data.") from exc

    if not isinstance(data, (bytes, bytearray)) or not data:
        raise RuntimeError("Gemini TTS returned invalid audio bytes.")
    return bytes(data)


def render_gemini_tts(
    text: str,
    output_mp3: str | Path,
    *,
    voice: str | None = None,
    model: str | None = None,
    style: str | None = None,
    bitrate: str = "128k",
    language: str = "zh-CN",
    delivery_mode: str = "casual_explanation",
    speaker_mode: str = "single",
) -> Path:
    script = (text or "").strip()
    if not script:
        raise ValueError("TTS text is empty.")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set.")

    client = genai.Client(api_key=api_key)
    route = resolve_tts_route(
        language,
        delivery_mode=delivery_mode,
        speaker_mode="single" if speaker_mode == "dual" else speaker_mode,
    )
    model_name = model or route.model
    voice_name = voice or route.voice
    style_text = style or route.style

    if speaker_mode == "dual":
        turns = _parse_dual_speaker_script(script)
        data = _render_dual(
            client,
            turns,
            model_name=model_name,
            style_text=style_text,
        )
    else:
        data = _render_single(
            client,
            script,
            model_name=model_name,
            voice_name=voice_name,
            style_text=style_text,
        )

    target = Path(output_mp3)
    target.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="abel-gemini-tts-") as tmp:
        wav = Path(tmp) / "speech.wav"
        wav.write_bytes(data)
        wav_to_mp3(wav, target, bitrate=bitrate)

    return target
