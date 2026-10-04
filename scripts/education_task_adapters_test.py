import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from education_task_adapters import prepare,require_source

def main():
    p=prepare("translation",{"text":"你好"})
    assert p["task_type"]=="translation"
    require_source(p)
    try: prepare("unknown",{})
    except ValueError: pass
    else: raise AssertionError
    try: require_source({"source_of_truth":"Gemini"})
    except ValueError: pass
    else: raise AssertionError
    print("education_task_adapters_test: PASS")
if __name__=="__main__": main()
