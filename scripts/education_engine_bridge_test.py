import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from education_engine_bridge import prepare_local,local_available

def main():
    assert local_available("chinese_writing_correction")
    out=prepare_local("chinese_writing_correction",{"text":"我喜欢学习中文","target_level":"HSK6","register":"neutral"})
    assert out["cache_key"] and out["prompt"]
    assert not local_available("translation")
    assert prepare_local("translation",{"text":"x"})["execution"]=="provider_required"
    print("education_engine_bridge_test: PASS")
if __name__=="__main__": main()
