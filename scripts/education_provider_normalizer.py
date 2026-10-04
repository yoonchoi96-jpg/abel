#!/usr/bin/env python3
"""Normalize heterogeneous provider responses into an Abel envelope."""
from __future__ import annotations
from typing import Any

SCHEMA="abel.education.provider-response.v1"

def normalize(model:str, raw:dict[str,Any])->dict[str,Any]:
    if not isinstance(raw,dict): raise ValueError("provider response must be an object")
    if model=="gpt":
        text=_gpt_text(raw)
    elif model=="claude":
        text=_claude_text(raw)
    elif model in ("deepseek","perplexity"):
        text=_chat_text(raw)
    elif model=="gemini":
        text=_gemini_text(raw)
    else:
        raise ValueError(f"unsupported_provider:{model}")
    return {"schema_version":SCHEMA,"provider":model,"status":"success","text":text,"raw":raw}

def _gpt_text(r):
    if isinstance(r.get("output_text"),str): return r["output_text"]
    for item in r.get("output",[]):
        for c in item.get("content",[]) if isinstance(item,dict) else []:
            if isinstance(c,dict) and isinstance(c.get("text"),str): return c["text"]
    return ""

def _claude_text(r):
    return "".join(x.get("text","") for x in r.get("content",[]) if isinstance(x,dict))

def _chat_text(r):
    c=(r.get("choices") or [{}])[0]
    m=c.get("message") or {}
    return m.get("content","") if isinstance(m.get("content",""),str) else ""

def _gemini_text(r):
    out=[]
    for c in r.get("candidates",[]):
        for p in (c.get("content") or {}).get("parts",[]):
            if isinstance(p,dict) and isinstance(p.get("text"),str): out.append(p["text"])
    return "".join(out)
