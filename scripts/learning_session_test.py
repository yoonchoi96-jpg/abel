from scripts.learning_session import connect, record_session, summary
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as t:
    db=Path(t)/"x.db"
    record_session({
        "language":"zh-CN","session_type":"listening","resource_id":"l1",
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
print("learning_session_test: OK")
