#!/usr/bin/env python3
import os, wave
from google import genai
from google.genai import types

SCRIPT = """各位听众，近日，我国首个自主研发的深远海浮式风电示范项目在广东阳江海域正式并网发电。这一标志性工程的投产，不仅填补了我国在深远海风力发电领域的技术空白，更意味着海洋清洁能源开发迈出了实质性的一步。与传统的近海固定式风电相比，深远海区域的风能资源更为丰富稳定，但施工难度和运维成本也成倍攀升。为此，项目研发团队攻克了抗超强台风、超深水动态电缆疲劳寿命等多项核心技术难题，首次采用了新型自适应漂浮基础结构。即便遭遇十七级台风等极端恶劣海况，发电机组依然能够保持高稳定性运行。据测算，该项目年发电量预计将突破八千万千瓦时，每年可节约标煤约两万四千吨，减少二氧化碳排放近六万吨。业内专家指出，虽然目前深远海风电的初始建造成本依然居高不下，但随着上下游产业链协同效应逐步显现，综合开发成本有望在未来五年内下降百分之三十以上。这一技术的规模化应用，将为沿海经济发达地区的能源结构转型提供强有力的战略支撑。"""

PROMPT = """请把下面的中文 HSK6 听力稿，读成一个真实的中国成年人在日常交流中向朋友或同学介绍一个有意思的话题。
只使用普通话中文发声，最终音频中不要出现任何英文，也不要朗读本段指令。
不要像新闻主播、广播员、老师、教授、播音员、有声书旁白或正式配音。
发音保持标准、清楚，但整体要放松、自然、像真实的人在聊天时认真讲一件事情。
必须完整保留下面听力稿的原文、词汇和事实，不要改写、翻译或删减。
语速自然偏快，大约每分钟 280 到 310 个汉字，不要为了学习者故意放慢。
保持连续自然的口语流动，使用真实说话时的短呼吸组和简短停顿。
根据句子的意思自然改变语调和节奏，不要每一句都使用播音腔。
有些句子可以平稳地陈述，有些句子可以自然地加强语气，但不要表演。
不要使用夸张的播音腔、正式演讲感、戏剧性停顿、虚假的犹豫、过多语气词或刻意热情的语气。
最重要的是：听起来应该像一个受过良好教育的中国人，用自然的日常普通话把这个话题讲给熟人听，而不是在朗读一篇稿子。

听力稿：
""" + SCRIPT

def main():
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    resp = client.models.generate_content(
        model="gemini-3.8-flash-tts",
        contents=[types.Content(role="user", parts=[types.Part.from_text(text=PROMPT)])],
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
    print(f"PASS casual Mandarin TTS: {len(data)} bytes; duration={len(data)/(24000*2):.2f}s")

if __name__ == "__main__":
    main()
