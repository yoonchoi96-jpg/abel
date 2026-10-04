#!/usr/bin/env python3
"""Provider execution facade: one safe entry point for Router -> adapter."""
from __future__ import annotations
from typing import Any, Callable
from education_provider_payloads import build
from education_provider_normalizer import normalize
from education_execution_policy import next_action

def execute_provider(model:str, payload:dict[str,Any], provider_call:Callable[[str,dict[str,Any]],dict[str,Any]], *, allow_api_call=False, retry_limit=0, fallback_available=False)->dict[str,Any]:
    if not allow_api_call:
        return {"schema_version":"abel.education.provider-facade.v1","status":"dry_run","model":model,"payload":build(model,payload)}
    attempts=0
    while True:
        attempts+=1
        try:
            raw=provider_call(model,build(model,payload))
            if not isinstance(raw,dict): raise ValueError("provider response must be an object")
            return {"schema_version":"abel.education.provider-facade.v1","status":"executed","model":model,"attempts":attempts,"response":normalize(model,raw)}
        except Exception as exc:
            action=next_action(exc,retry_count=attempts-1,max_retries=retry_limit,fallback_available=fallback_available)
            if action=="retry": continue
            return {"schema_version":"abel.education.provider-facade.v1","status":"fallback" if action=="fallback" else "failed","model":model,"attempts":attempts,"error":str(exc)}

