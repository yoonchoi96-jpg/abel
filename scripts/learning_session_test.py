from scripts.learning_session import connect, record_session, summary
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as t:
    db=Path(t)/"x.db"
    record_session({"language":"zh-CN","session_type":"listening","score":80,"total":10,"correct":8},db)
    s=summary("zh-CN",db)
    assert s["session_types"][0]["n"]==1
print("learning_session_test: OK")
