#!/usr/bin/env python3
from education_task_adapters import prepare

def test_provider_task_prompts():
    cases=[
        ("translation",{"text":"你好","target_language":"ko-KR"}),
        ("chinese_explanation",{"text":"他已经走了"}),
        ("vocabulary_review",{"words":["维护","维持"]}),
        ("listening_transcript_analysis",{"transcript":"他说得很快。"}),
        ("speaking_feedback",{"transcript":"我昨天去了北京。"}),
        ("current_facts_research",{"question":"What is the current HSK 3.0 structure?"}),
    ]
    for task,payload in cases:
        out=prepare(task,payload)
        assert out["task_type"]==task
        assert isinstance(out["prompt"],str) and out["prompt"]

if __name__=="__main__":
    test_provider_task_prompts()
    print("education_task_prompt_test: OK")
