import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from education_local_dispatch import dispatch

def main():
    out=dispatch("chinese_writing_correction",{"text":"我喜欢学习中文","language":"zh-CN","target_level":"HSK6"})
    assert out["local"] and out["result"]["cache_key"]
    out=dispatch("translation",{"text":"你好"})
    assert not out["local"]
    print("education_local_dispatch_test: PASS")
if __name__=="__main__": main()
