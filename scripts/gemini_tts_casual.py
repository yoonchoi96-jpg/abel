#!/usr/bin/env python3
"""Canonical single-speaker Gemini TTS smoke sample for Abel."""
from __future__ import annotations

from pathlib import Path

from gemini_tts_renderer import render_gemini_tts

SCRIPT = """各位听众，近日，我国首个自主研发的深远海浮式风电示范项目在广东阳江海域正式并网发电。这一标志性工程的投产，不仅填补了我国在深远海风力发电领域的技术空白，更意味着海洋清洁能源开发迈出了实质性的一步。与传统的近海固定式风电相比，深远海区域的风能资源更为丰富稳定，但施工难度和运维成本也成倍攀升。为此，项目研发团队攻克了抗超强台风、超深水动态电缆疲劳寿命等多项核心技术难题，首次采用了新型自适应漂浮基础结构。即便遭遇十七级台风等极端恶劣海况，发电机组依然能够保持高稳定性运行。据测算，该项目年发电量预计将突破八千万千瓦时，每年可节约标煤约两万四千吨，减少二氧化碳排放近六万吨。业内专家指出，虽然目前深远海风电的初始建造成本依然居高不下，但随着上下游产业链协同效应逐步显现，综合开发成本有望在未来五年内下降百分之三十以上。这一技术的规模化应用，将为沿海经济发达地区的能源结构转型提供强有力的战略支撑。"""

def main() -> None:
    output = Path("gemini_tts_hsk6_casual.mp3")
    render_gemini_tts(
        SCRIPT,
        output,
        language="zh-CN",
        delivery_mode="casual_explanation",
        speaker_mode="single",
    )
    print(f"PASS canonical Abel TTS route: {output} ({output.stat().st_size} bytes)")

if __name__ == "__main__":
    main()
