FROM python:3.12-slim

WORKDIR /app

COPY requirements-mcp.txt .
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements-mcp.txt

COPY scripts/abel_mcp_server.py .
COPY scripts/gemini_tts_renderer.py .
COPY scripts/audio_style_profiles.py .
COPY scripts/hsk_evaluation_engine.py .
COPY scripts/writing_correction_engine.py .
COPY scripts/multilingual_writing_engine.py .

ENV PYTHONUNBUFFERED=1
ENV PORT=8080

CMD ["python", "abel_mcp_server.py"]
