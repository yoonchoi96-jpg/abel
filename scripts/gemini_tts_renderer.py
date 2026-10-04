#!/usr/bin/env python3
"""Gemini TTS renderer for Abel.

Gemini 3.8 Flash TTS returns a complete WAV file for unary requests.
The Drive/Apps Script layer is storage-only.
"""
from __future__ import annotations

import os
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
        speaker_mode=speaker_mode,
    )
    model_name = model or route.model
    voice_name = voice or route.voice
    style_text = style or route.style

    response = client.models.generate_content(
        model=model_name,
        contents=[types.Content(
            role="user",
            parts=[types.Part.from_text(text=f"{style_text}\n\n{script}")],
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

    try:
        data = response.candidates[0].content.parts[0].inline_data.data
    except (AttributeError, IndexError, TypeError) as exc:
        raise RuntimeError("Gemini TTS response did not contain audio data.") from exc

    if not isinstance(data, (bytes, bytearray)) or not data:
        raise RuntimeError("Gemini TTS returned invalid audio bytes.")

    target = Path(output_mp3)
    target.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="abel-gemini-tts-") as tmp:
        wav = Path(tmp) / "speech.wav"
        wav.write_bytes(bytes(data))
        wav_to_mp3(wav, target, bitrate=bitrate)

    return target
