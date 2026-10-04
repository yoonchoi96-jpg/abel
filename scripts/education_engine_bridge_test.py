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
    assert qa["version"]
    assert qa["status"] in {"PASS","REVIEW","FAIL"}
    assert not local_available("translation")
    assert prepare_local("translation",{"text":"x"})["execution"]=="provider_required"
    print("education_engine_bridge_test: PASS")
if __name__=="__main__": main()
