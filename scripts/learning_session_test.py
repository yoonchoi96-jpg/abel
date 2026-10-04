from scripts.learning_session import connect, record_session, summary
from scripts.review_state_engine import due_items
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as t:
    db=Path(t)/"x.db"
    record_session({
        "language":"zh-CN","session_type":"listening","resource_id":"l1","started_at":"2026-10-03T00:00:00+00:00",
        "level":"HSK6","score":80,"total":10,"correct":8,
        "payload":{"results":[
            {"question_id":"q1","correct":False,"error_type":"vocabulary"},
            {"question_id":"q2","correct":True},
            {"question_id":"q3","correct":False,"error_type":"comprehension"},
        ]}
    },db)
    s=summary("zh-CN",db)
    assert s["session_types"][0]["n"]==1
    assert len(s["practice_errors"])==2
    assert s["practice_errors"][0]["count"]==1
    states=connect(db).execute("SELECT question_id,correct_count,wrong_count FROM review_states ORDER BY question_id").fetchall()
    assert [(r["question_id"],r["correct_count"],r["wrong_count"]) for r in states] == [("q1",0,1),("q2",1,0),("q3",0,1)]
    assert len(due_items("zh-CN",db,now="2026-10-04T00:00:00+00:00")) == 2
print("learning_session_test: OK")
