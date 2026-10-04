#!/usr/bin/env python3
"""Gemini TTS renderer for Abel.

Generates 24 kHz mono PCM with Gemini TTS and converts it to MP3 locally.
The Drive/Apps Script layer is intentionally storage-only.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

from google import genai
from google.genai import types

DEFAULT_MODEL = "gemini-3.8-flash-tts"
DEFAULT_VOICE = "Kore"
SAMPLE_RATE = 24000
CHANNELS = 1
SAMPLE_WIDTH = 2


def pcm_to_wav(pcm: bytes, output_path: str | Path) -> Path:
    if not pcm:
        raise ValueError("Gemini TTS returned empty PCM audio.")
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm)
    return path


def wav_to_mp3(wav_path: str | Path, mp3_path: str | Path, bitrate: str = "128k") -> Path:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is required to convert Gemini PCM/WAV to MP3.")

    source = Path(wav_path)
    target = Path(mp3_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(source),
            "-codec:a", "libmp3lame",
            "-b:a", bitrate,
            "-ar", str(SAMPLE_RATE),
            "-ac", str(CHANNELS),
            str(target),
        ],
        check=True,
    )
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
) -> Path:
    script = (text or "").strip()
    if not script:
        raise ValueError("TTS text is empty.")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set.")

    client = genai.Client(api_key=api_key)
    model_name = model or os.getenv("GEMINI_TTS_MODEL", DEFAULT_MODEL)
    voice_name = voice or os.getenv("GEMINI_TTS_VOICE", DEFAULT_VOICE)
    style_text = style or os.getenv(
        "GEMINI_TTS_STYLE",
        "Standard Mandarin. Natural, clear, educated HSK listening delivery. "
        "Do not sound like a news anchor. Preserve every word and fact. "
        "Use natural phrasing and restrained prosody; do not add fillers.",
    )

    prompt = f"{style_text}\n\nRead the following Chinese script exactly as written:\n{script}"

    response = client.models.generate_content(
        model=model_name,
        contents=[types.Content(
            role="user",
            parts=[types.Part.from_text(text=prompt)],
        )],
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=voice_name
                    )
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
        pcm_to_wav(bytes(data), wav)
        wav_to_mp3(wav, target, bitrate=bitrate)

    return target
