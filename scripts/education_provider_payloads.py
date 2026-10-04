#!/usr/bin/env python3
"""Provider-specific request builders for Abel Education Router."""
from __future__ import annotations
from typing import Any

def _messages(payload):
    if "messages" in payload: return payload["messages"]
    text=payload.get("prompt") or payload.get("input") or payload.get("text","")
    return [{"role":"user","content":text}]

def build(model:str,payload:dict[str,Any])->dict[str,Any]:
    messages=_messages(payload)
    model_name=payload.get("model")
    if model=="gpt":
        return {"model":model_name or "gpt-5.6","input":messages,"store":False}
    if model=="claude":
        system=payload.get("system")
        out={"model":model_name or "claude-sonnet-4-5","max_tokens":payload.get("max_tokens",4096),"messages":messages}
        if system: out["system"]=system
        return out
    if model=="deepseek":
        return {"model":model_name or "deepseek-chat","messages":messages,"temperature":payload.get("temperature",0)}
    if model=="perplexity":
        return {"model":model_name or "sonar","messages":messages}
    if model=="gemini":
        text=payload.get("prompt") or payload.get("input") or payload.get("text","")
        return {"contents":[{"role":"user","parts":[{"text":text}]}]}
    raise ValueError(f"unsupported_provider:{model}")
