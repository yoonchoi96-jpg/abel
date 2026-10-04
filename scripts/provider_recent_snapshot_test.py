#!/usr/bin/env python3
import tempfile
from pathlib import Path
from learning_session import record_provider_event, provider_recent
from learning_snapshot import build_snapshot

def test_recent_provider_results():
    with tempfile.TemporaryDirectory() as d:
        db=Path(d)/"learning.db"
        record_provider_event("zh-CN","translation",{"status":"executed","result":{"text":"你好"}},model="deepseek",cache_key="k1",db_path=db)
        recent=provider_recent("zh-CN",db)
        assert len(recent)==1
        assert recent[0]["output"]["result"]["text"]=="你好"
        snap=build_snapshot("zh-CN",db)
        assert len(snap["recent_provider_results"])==1

if __name__=="__main__":
    test_recent_provider_results()
    print("provider_recent_snapshot_test: OK")
