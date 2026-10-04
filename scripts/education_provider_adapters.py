#!/usr/bin/env python3
"""Provider adapter contracts for Abel Education Router.

Adapters deliberately use environment variables for credentials and expose a
uniform JSON-object interface. No provider is called unless configured and
the caller explicitly invokes the adapter.
"""
from __future__ import annotations
import os
from typing import Any, Callable

SCHEMA="abel.education.provider-adapter.v1"

ENV_KEYS={
    "gemini":"GEMINI_API_KEY",
    "deepseek":"DEEPSEEK_API_KEY",
    "openai":"OPENAI_API_KEY",
    "gpt":"OPENAI_API_KEY",
    "claude":"ANTHROPIC_API_KEY",
    "anthropic":"ANTHROPIC_API_KEY",
    "perplexity":"PERPLEXITY_API_KEY",
}

def required_env(model:str)->str|None:
    return ENV_KEYS.get(model)

def configured(model:str, env:dict[str,str]|None=None)->bool:
    env=env or os.environ
    key=required_env(model)
    return bool(key and env.get(key))

def contract(model:str, *, env:dict[str,str]|None=None)->dict[str,Any]:
    key=required_env(model)
    return {
        "schema_version":SCHEMA,
        "model":model,
        "credential_env":key,
        "configured":configured(model,env),
        "dry_run":True,
        "api_call_allowed":False,
        "note":"Provider-specific HTTP/SDK invocation is intentionally not performed by this contract layer.",
    }

def make_stub(model:str)->Callable[[dict[str,Any]],dict[str,Any]]:
    def _stub(payload:dict[str,Any])->dict[str,Any]:
        return {"schema_version":SCHEMA,"model":model,"status":"dry_run",
                "configured":configured(model),"payload":payload}
    return _stub
