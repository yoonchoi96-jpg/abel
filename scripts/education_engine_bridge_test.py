import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from education_engine_bridge import prepare_local,local_available

def main():
    assert local_available("chinese_writing_correction")
    out=prepare_local("chinese_writing_correction",{"text":"我喜欢学习中文","target_level":"HSK6","register":"neutral"})
    assert out["cache_key"] and out["prompt"]

    plan=prepare_local("adaptive_learning_plan",{"candidates":[{"id":"r1","kind":"reading","priority":2}]})
    assert plan["count"]==1

    qa=prepare_local("hsks_exam_qa",{"questions":[{"number":1,"part":"listening","stem":"x","options":["A a","B b","C c","D d"],"answer":"A"}],"expected_total":1})
    assert qa["engine"]=="Abel HSK Evaluation Engine"

    listening={"id":"l1","language":"zh-CN","level":"HSK6","audio":"a.mp3","questions":[{"id":"q1","type":"choice"}],"answer_key":{"q1":"A"}}
    out=prepare_local("listening_practice",{"resource":listening,"answers":{"q1":"A"}})
    assert out["score"]==100

    reading={"id":"r1","language":"zh-CN","level":"HSK6","passage":"短文","questions":[{"id":"q1","type":"choice"}],"answer_key":{"q1":"A"}}
    out=prepare_local("reading_practice",{"resource":reading,"answers":{"q1":"A"}})
    assert out["score"]==100

    writing={"id":"w1","language":"zh-CN","level":"HSK6","prompt":"请写一段话"}
    out=prepare_local("writing_practice",{"resource":writing})
    assert out["status"]=="ready_for_correction"

    mock={"id":"m1","language":"zh-CN","level":"HSK6","exam_system":"HSK3.0","sections":[{"kind":"reading","unit_id":"r1"}]}
    unit={"id":"r1","kind":"reading","language":"zh-CN","level":"HSK6","questions":[{"id":"q1","answer":"A"}]}
    out=prepare_local("mock_test",{"mock":mock,"units":[unit],"results":[{"unit_id":"r1","kind":"reading","total":1,"correct":1,"score":100}]})
    assert out["score"]==100

    out=prepare_local("error_review",{"results":[{"question_id":"q1","correct":False,"priority":2}]})
    assert out["count"]==1

    assert not local_available("translation")
    assert prepare_local("translation",{"text":"x"})["execution"]=="provider_required"
    print("education_engine_bridge_test: PASS")
if __name__=="__main__": main()
