#!/usr/bin/env python3
"""Provider execution policy: cheap, deterministic failure classification."""
from __future__ import annotations
from typing import Any

RETRYABLE_STATUS={408,409,425,429,500,502,503,504}
NONRETRYABLE_STATUS={400,401,403,404,422}

def classify_error(error:Any)->str:
    status=None
    if isinstance(error,dict): status=error.get("status") or error.get("http_status")
    if isinstance(status,int):
        if status in RETRYABLE_STATUS: return "retryable"
        if status in NONRETRYABLE_STATUS: return "non_retryable"
    s=str(error).lower()
    if any(x in s for x in ("timeout","temporarily","rate limit","429","503","connection reset")):
        return "retryable"
    if any(x in s for x in ("invalid api key","unauthorized","forbidden","bad request")):
        return "non_retryable"
    return "unknown"

def next_action(error:Any, *, retry_count:int, max_retries:int, fallback_available:bool)->str:
    c=classify_error(error)
    if c=="retryable" and retry_count<max_retries: return "retry"
    if fallback_available: return "fallback"
    return "fail"
