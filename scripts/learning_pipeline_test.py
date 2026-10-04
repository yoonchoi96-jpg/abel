from pathlib import Path
import sys, tempfile
sys.path.insert(0, str(Path(__file__).resolve().parent))
from learning_pipeline import run

def main():
    results=[{
      "unit_id":"read-1","kind":"reading","language":"zh-CN","level":"HSK6",
      "total":2,"correct":1,"score":50,
      "results":[
        {"question_id":"q1","correct":False,"error_type":"vocabulary"},
        {"question_id":"q2","correct":True}
      ]
    }]
    with tempfile.TemporaryDirectory() as t:
        out=run(results,Path(t)/"x.db",{"reading":1})
        assert out["sessions_recorded"]==1
        assert out["error_review"]["count"]==1
        assert out["adaptive_plan"]["count"]==1
        assert out["adaptive_plan"]["items"][0]["id"]=="q1"
        assert out["snapshot"]["learning_sessions"]["session_types"][0]["n"]==1
    print("learning_pipeline_test: PASS")