#!/usr/bin/env python3
"""Secret-safe HTTP provider adapters.

Real calls are opt-in via allow_api_call=True. The executor should remain the
gatekeeper for cache/budget policy; adapters only translate a request to a
provider and normalize the JSON response. API keys are read from env only.
"""
from __future__ import annotations
import json, os
from urllib.request import Request, urlopen
from typing import Any

ENV_KEYS={"gemini":"GEMINI_API_KEY","deepseek":"DEEPSEEK_API_KEY","gpt":"OPENAI_API_KEY","claude":"ANTHROPIC_API_KEY","perplexity":"PERPLEXITY_API_KEY"}

def _key(model, env=None):
    env=env or os.environ
    name=ENV_KEYS.get(model)
    if not name or not env.get(name):
        raise RuntimeError(f"provider_not_configured:{model}")
    return env[name]

def build_request(model:str,payload:dict[str,Any],*,env=None)->Request:
    key=_key(model,env)
    if model in ("gpt","claude","deepseek","perplexity"):
        urls={"gpt":"https://api.openai.com/v1/responses","claude":"https://api.anthropic.com/v1/messages","deepseek":"https://api.deepseek.com/chat/completions","perplexity":"https://api.perplexity.ai/chat/completions"}
        return Request(urls[model],data=json.dumps(payload,ensure_ascii=False).encode(),headers={"Content-Type":"application/json","Authorization":f"Bearer {key}"},method="POST")
    raise ValueError("gemini_requires_provider_specific_request_shape")

def call(model:str,payload:dict[str,Any],*,timeout=60,allow_api_call=False,env=None)->dict[str,Any]:
    if not allow_api_call:
        return {"schema_version":"abel.education.provider-call.v1","status":"dry_run","model":model}
    req=build_request(model,payload,env=env)
    with urlopen(req,timeout=timeout) as resp:
        body=resp.read().decode()
        return {"schema_version":"abel.education.provider-call.v1","status":"executed","model":model,"http_status":resp.status,"raw":json.loads(body)}
