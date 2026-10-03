#!/usr/bin/env python3
import os, wave
from google import genai

DIALOGUE = [
    ("男", "你最近有没有看到那个深远海浮式风电项目的新闻？听说已经正式并网发电了。"),
    ("女", "看到了。我一开始还挺意外的，因为深远海风电听起来就比普通的近海项目难得多。"),
    ("男", "对，尤其是施工和后期维护。海上风浪那么大，设备又离岸这么远，成本肯定不低。"),
    ("女", "没错。不过这次比较值得关注的是，他们解决了几个关键技术问题。比如抗超强台风，还有超深水动态电缆的疲劳寿命。"),
    ("男", "我看到报道里还提到了一种自适应漂浮基础。这个东西是不是能让机组在恶劣海况下保持稳定？"),
    ("女", "对。即使遇到十七级台风，发电机组也能维持比较高的运行稳定性。这样一来，深远海风电的实际应用就有了更大的空间。"),
    ("男", "而且如果以后规模扩大，成本应该也会慢慢降下来吧？"),
    ("女", "专家的判断也是这样。现在初始建造成本还是比较高，但随着上下游产业链逐渐成熟，综合开发成本有望明显下降。"),
    ("男", "那它的意义就不只是多建几个风电机组了，而是可能推动沿海地区整个能源结构的调整。"),
    ("女", "对，我觉得真正值得关注的就是这一点。技术成熟以后，清洁能源的开发方式可能会发生很大的变化。"),
]

PROMPT = """请把下面的内容制作成一段真实、自然的中文男女对话。
只使用中国大陆标准普通话发声，最终音频中绝对不要出现英文。
这是两个真实的中国成年人在聊天，不是新闻播报、课堂讲课、正式演讲或有声书朗读。

男：男性成年人，普通话标准，语气自然、放松、聪明。
女：女性成年人，普通话标准，语气自然、放松、聪明。
两个人要有明显不同的声音，并且像真正认识的人在交流。

最重要的是自然的对话节奏：
- 不要把每一轮都读成完整、工整的文章句子。
- 根据对方刚说的话自然回应，有时简短，有时展开。
- 语调要随着疑问、确认、补充、转折和结论自然变化。
- 停顿短而自然，不要每句话之间机械停顿。
- 不要夸张热情，不要表演，不要播音腔。
- 不要添加原文之外的内容，也不要删改下面任何一句话。
- 这是 HSK6 听力材料，所以保留较高的信息密度和高级词汇。
- 整体速度接近真实中国成年人正常聊天，但要保证学习者能够清楚听懂。

请严格按照下面标注的男女顺序发声。"""

def main():
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    parts = [
        {"text": PROMPT},
    ]
    for speaker, text in DIALOGUE:
        parts.append({
            "text": text,
            "speech_metadata": {
                "speaker": speaker,
                "style": (
                    "自然、放松、像和熟人聊天"
                    if speaker == "男"
                    else "自然、放松、像和熟人聊天"
                ),
            },
        })

    resp = client.models.generate_content(
        model="gemini-3.8-flash-tts",
        contents=[{"role": "user", "parts": parts}],
        config={
            "response_modalities": ["AUDIO"],
            "speech_config": {
                "language_code": "cmn-CN",
                "multi_speaker_voice_config": {
                    "speaker_voice_configs": [
                        {
                            "speaker": "男",
                            "voice_config": {
                                "prebuilt_voice_config": {"voice_name": "Puck"}
                            },
                        },
                        {
                            "speaker": "女",
                            "voice_config": {
                                "prebuilt_voice_config": {"voice_name": "Kore"}
                            },
                        },
                    ]
                },
            },
        },
    )

    data = resp.candidates[0].content.parts[0].inline_data.data
    with wave.open("gemini_tts_hsk6_dialogue.wav", "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(data)

    print(f"PASS two-speaker Mandarin TTS: {len(data)} bytes; duration={len(data)/(24000*2):.2f}s")

if __name__ == "__main__":
    main()
