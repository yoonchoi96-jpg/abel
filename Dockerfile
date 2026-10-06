# Abel MCP production runtime
# Gemini TTS production runtime
# Drive bridge production routing enabled
FROM python:3.12-slim

WORKDIR /app

COPY requirements-mcp.txt .
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements-mcp.txt \
    && pip install --no-cache-dir "google-genai>=2.0,<3" "google-auth>=2.0,<3"

COPY scripts/abel_mcp_server.py .
COPY scripts/drive_audio_uploader.py .
COPY scripts/learning_router.py .
COPY scripts/gemini_tts_renderer.py .
COPY scripts/tts_router.py .
COPY scripts/audio_style_profiles.py .
COPY scripts/hsk_evaluation_engine.py .
COPY scripts/hsk30_evaluation_engine.py .
COPY scripts/writing_correction_engine.py .
COPY scripts/multilingual_writing_engine.py .

ENV PYTHONUNBUFFERED=1
ENV PORT=8080

CMD ["python", "abel_mcp_server.py"]
