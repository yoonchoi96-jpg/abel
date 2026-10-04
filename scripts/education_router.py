#!/usr/bin/env python3
"""Abel Education Router: deterministic task-to-model routing with cache metadata."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from typing import Any

SCHEMA="abel.education.router.v1"

ROUTES={
 "chinese_writing_correction":{"primary":"gemini","fallback":["claude","gpt"],"cache":True,"batchable":True},
 "chinese_explanation":{"primary":"gemini","fallback":["gpt","claude"],"cache":True,"batchable":True},
 "hsks_exam_qa":{"primary":"claude","fallback":["gpt","gemini"],"cache":True,"batchable":True},
 "adaptive_learning_plan":{"primary":"gpt","fallback":["gemini","claude"],"cache":True,"batchable":False},
 "vocabulary_review":{"primary":"deepseek","fallback":["gemini","gpt"],"cache":True,"batchable":True},
 "listening_transcript_analysis":{"primary":"gemini","fallback":["gpt","claude"],"cache":True,"batchable":True},
 "current_facts_research":{"primary":"perplexity","fallback":["gpt"],"cache":False,"batchable":True},
 "naver_dictionary_collection":{"primary":"naver_ai","fallback":[],"cache":True,"batchable":True},
 "translation":{"primary":"deepseek","fallback":["gpt","gemini"],"cache":True,"batchable":True},
 "speaking_feedback":{"primary":"gpt","fallback":["gemini","claude"],"cache":True,"batchable":False},
 "listening_practice":{"primary":"gemini","fallback":["gpt","claude"],"cache":True,"batchable":True},
 "reading_practice":{"primary":"gemini","fallback":["gpt","claude"],"cache":True,"batchable":True},
 "writing_practice":{"primary":"gemini","fallback":["claude","gpt"],"cache":True,"batchable":True},
 "mock_test":{"primary":"gpt","fallback":["gemini","claude"],"cache":True,"batchable":False},
 "error_review":{"primary":"gpt","fallback":["gemini","claude"],"cache":True,"batchable":True},
}

def cache_key(task_type:str,payload:dict[str,Any],prompt_version="1"):
    raw=json.dumps({"task_type":task_type,"payload":payload,"prompt_version":prompt_version},
                   ensure_ascii=False,sort_keys=True,separators=(",",":"))
    return hashlib.sha256(raw.encode()).hexdigest()

def route(task_type:str,payload:dict[str,Any],*,prompt_version="1",force_model=None):
    if task_type not in ROUTES:
        raise ValueError("unknown task_type: "+task_type)
    spec=ROUTES[task_type]
    models=[force_model] if force_model else [spec["primary"],*spec["fallback"]]
    return {
      "schema_version":SCHEMA,"task_type":task_type,"model_chain":models,
      "primary_model":models[0],"cache_enabled":spec["cache"],"batchable":spec["batchable"],
      "cache_key":cache_key(task_type,payload,prompt_version),"source_of_truth":"Abel",
      "api_call_policy":"cache_hit_first; call only on miss; retry failed stage only",
    }

if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("task_type"); p.add_argument("payload")
    p.add_argument("--prompt-version",default="1"); p.add_argument("--force-model"); p.add_argument("--out",required=True)
    a=p.parse_args(); payload=json.loads(Path(a.payload).read_text(encoding="utf-8"))
    out=route(a.task_type,payload,prompt_version=a.prompt_version,force_model=a.force_model)
    Path(a.out).write_text(json.dumps(out,ensure_ascii=False,indent=2)+"
",encoding="utf-8"); print(a.out)
