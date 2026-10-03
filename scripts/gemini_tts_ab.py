#!/usr/bin/env python3
"""Experimental Gemini 3.8 Flash TTS A/B renderer for Abel."""
from __future__ import annotations
import os, wave
from google import genai
from google.genai import types

SCRIPT = """各位听众，近日，我国首个自主研发的深远海浮式风电示范项目在广东阳江海域正式并网发电。这一标志性工程的投产，不仅填补了我国在深远海风力发电领域的技术空白，更意味着海洋清洁能源开发迈出了实质性的一步。

与传统的近海固定式风电相比，深远海区域的风能资源更为丰富稳定，但施工难度和运维成本也成倍攀升。为此，项目研发团队攻克了抗超强台风、超深水动态电缆疲劳寿命等多项核心技术难题，首次采用了新型自适应漂浮基础结构。即便遭遇十七级台风等极端恶劣海况，发电机组依然能够保持高稳定性运行。

据测算，该项目年发电量预计将突破八千万千瓦时，每年可节约标煤约两万四千吨，减少二氧化碳排放近六万吨。业内专家指出，虽然目前深远海风电的初始建造成本依然居高不下，但随着上下游产业链协同效应逐步显现，综合开发成本有望在未来五年内下降百分之三十以上。这一技术的规模化应用，将为沿海经济发达地区的能源结构转型提供强有力的战略支撑。"""

PROMPT = """Read the following Mandarin HSK6 listening script as a skilled native Chinese radio/news presenter speaking to real listeners, not as someone mechanically reading an essay.
Use a calm, intelligent, professional broadcast voice. Keep the exact wording and all facts.
Vary sentence-level intonation naturally according to meaning. Do not give every sentence the same falling contour.
Give new, contrastive, causal, and concluding information appropriate emphasis without sounding theatrical.
Keep pauses SHORT and economical. Pause mainly at sentence boundaries or genuinely important information boundaries; do not insert dramatic pauses between ordinary phrases.
Maintain a fluent educational-radio pace. Do not slow down to emphasize every clause.
Avoid metronomic timing, evenly spaced pauses, exaggerated emotion, fake hesitation, and unnecessary fillers.
Target a natural HSK6 listening pace rather than a slow language-learning narration.
The result should sound like a human professional recording a real educational news segment for HSK6 learners: clear and controlled, but organically paced and expressive."""

def main():
    key=os.environ["GEMINI_API_KEY"]
    client=genai.Client(api_key=key)
    resp=client.models.generate_content(
        model="gemini-3.8-flash-tts",
        contents=[types.Content(role="user", parts=[types.Part.from_text(text=PROMPT + "\n\nSCRIPT:\n" + SCRIPT)])],
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")
                )
            ),
        ),
    )
    part=resp.candidates[0].content.parts[0]
    data=part.inline_data.data
    mime=part.inline_data.mime_type or ""
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError(f"Unexpected audio payload type: {type(data)}")
    # Gemini TTS returns raw 24 kHz mono PCM for this path.
    with wave.open("gemini_tts_hsk6_ab_v2.wav","wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(data)
    duration = len(data) / (24000 * 2)
print(f"PASS Gemini TTS v2 generated {len(data)} bytes; mime={mime}; duration={duration:.2f}s")
if duration < 45 or duration > 150:
    raise RuntimeError(f"FAIL: duration {duration:.2f}s outside HSK6 target range 45-150s")

if __name__=="__main__":
    main()
