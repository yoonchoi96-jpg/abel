import tempfile
from datetime import datetime, timezone
from pathlib import Path
from review_state_engine import apply_result, due_items

def test_review_progression_and_language_isolation():
    with tempfile.TemporaryDirectory() as d:
        db=str(Path(d)/"x.db"); t="2026-10-01T00:00:00+00:00"
        s=apply_result("zh-CN","q1","r1",False,kind="reading",at=t,db_path=db)
        assert s["wrong_count"]==1 and s["interval_days"]==0
        assert due_items("zh-CN",db,now=t)
        s=apply_result("zh-CN","q1","r1",True,at="2026-10-02T00:00:00+00:00",db_path=db)
        assert s["correct_count"]==1 and s["interval_days"]==2
        assert not due_items("zh-CN",db,now="2026-10-02T12:00:00+00:00")
        assert due_items("zh-CN",db,now="2026-10-04T00:00:00+00:00")
        assert due_items("zh-CN",db,now="2026-10-04T00:00:00+00:00")
        assert not due_items("fr-FR",db,now="2026-10-10T00:00:00+00:00")

def test_deterministic_and_mastered():
    with tempfile.TemporaryDirectory() as d:
        db=str(Path(d)/"x.db")
        t="2026-10-01T00:00:00+00:00"
        for i in range(5):
            apply_result("zh-CN","q1","r1",True,at=f"2026-10-0{1+i}T00:00:00+00:00",db_path=db)
        s=apply_result("zh-CN","q1","r1",True,at="2026-10-06T00:00:00+00:00",db_path=db)
        assert s["status"]=="mastered"
        assert s["consecutive_correct"]==6
