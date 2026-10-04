#!/usr/bin/env python3
import tempfile
from pathlib import Path
from learning_session import record_provider_event, provider_summary
from learning_snapshot import build_snapshot

def test_provider_history_and_snapshot():
    with tempfile.TemporaryDirectory() as d:
        db=Path(d)/"learning.db"
        record_provider_event("zh-CN","translation",{"status":"executed","text":"你好"},model="deepseek",cache_key="abc",db_path=db)
        s=provider_summary("zh-CN",db)
        assert s["events"][0]["task_type"]=="translation"
        snap=build_snapshot("zh-CN",db)
        assert snap["provider_learning"]["events"][0]["count"]==1

if __name__=="__main__":
    test_provider_history_and_snapshot()
    print("provider_learning_history_test: OK")
