#!/usr/bin/env python3
"""Provider registry and conservative execution metadata for Abel."""
from __future__ import annotations
from typing import Any

REGISTRY={
 "gemini":{"credential_env":"GEMINI_API_KEY","adapter":"gemini","batchable":True},
 "deepseek":{"credential_env":"DEEPSEEK_API_KEY","adapter":"deepseek","batchable":True},
 "gpt":{"credential_env":"OPENAI_API_KEY","adapter":"gpt","batchable":False},
 "claude":{"credential_env":"ANTHROPIC_API_KEY","adapter":"claude","batchable":False},
 "perplexity":{"credential_env":"PERPLEXITY_API_KEY","adapter":"perplexity","batchable":False},
}

def get(model:str)->dict[str,Any]:
    if model not in REGISTRY: raise ValueError(f"unknown_provider:{model}")
    return dict(REGISTRY[model])

def execution_plan(model_chain:list[str], *, cache_hit:bool, budget_units:float|None, estimated_units:float)->dict[str,Any]:
    if cache_hit: return {"status":"cache_hit","providers":[],"estimated_units":0}
    if budget_units is not None and estimated_units>budget_units:
        return {"status":"budget_blocked","providers":[],"estimated_units":estimated_units}
    providers=[]
    for model in model_chain:
        meta=get(model)
        providers.append({"model":model,"batchable":meta["batchable"],"credential_env":meta["credential_env"]})
    return {"status":"ready","providers":providers,"estimated_units":estimated_units}
