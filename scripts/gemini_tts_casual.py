#!/usr/bin/env python3
import os, wave
from google import genai
from google.genai import types

SCRIPT = """各位听众，近日，我国首个自主研发的深远海浮式风电示范项目在广东阳江海域正式并网发电。这一标志性工程的投产，不仅填补了我国在深远海风力发电领域的技术空白，更意味着海洋清洁能源开发迈出了实质性的一步。与传统的近海固定式风电相比，深远海区域的风能资源更为丰富稳定，但施工难度和运维成本也成倍攀升。为此，项目研发团队攻克了抗超强台风、超深水动态电缆疲劳寿命等多项核心技术难题，首次采用了新型自适应漂浮基础结构。即便遭遇十七级台风等极端恶劣海况，发电机组依然能够保持高稳定性运行。据测算，该项目年发电量预计将突破八千万千瓦时，每年可节约标煤约两万四千吨，减少二氧化碳排放近六万吨。业内专家指出，虽然目前深远海风电的初始建造成本依然居高不下，但随着上下游产业链协同效应逐步显现，综合开发成本有望在未来五年内下降百分之三十以上。这一技术的规模化应用，将为沿海经济发达地区的能源结构转型提供强有力的战略支撑。"""

PROMPT = """Read this Mandarin HSK6 script like a real Chinese adult casually explaining something interesting to a friend or classmate.
Do not sound like a news anchor, broadcaster, teacher, lecturer, audiobook narrator, or voice-over.
Use relaxed everyday standard Mandarin with clear pronunciation.
Sound spontaneous and comfortable rather than polished or performed.
Keep the exact wording and all facts.
Use a natural conversational pace around 280–310 Chinese characters per minute. Do not slow down for learners.
Use natural connected speech, varied rhythm, ordinary sentence endings, and subtle pitch movement.
Do not give every sentence a polished broadcast contour. Let some sentences be matter-of-fact and others naturally emphasized.
Use short natural breath groups and brief pauses, but keep the flow continuous.
Avoid announcer projection, formal presentation energy, dramatic pauses, theatrical emotion, fake hesitation, excessive fillers, exaggerated friendliness, and metronomic timing.
The result should sound like an educated Chinese person casually telling someone about this topic in everyday life while still speaking clear standard Mandarin."""

def main():
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    resp = client.models.generate_content(
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
    data = resp.candidates[0].content.parts[0].inline_data.data
    with wave.open("gemini_tts_hsk6_casual.wav", "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(data)
    print(f"PASS casual TTS: {len(data)} bytes; duration={len(data)/(24000*2):.2f}s")

if __name__ == "__main__":
    main()
