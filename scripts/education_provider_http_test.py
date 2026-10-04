import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from education_provider_http import call, build_request

def main():
    d=call("gpt",{"input":"x"},allow_api_call=False)
    assert d["status"]=="dry_run"
    try:
        build_request("gpt",{"input":"x"},env={})
    except RuntimeError as e:
        assert str(e)=="provider_not_configured:gpt"
    else:
        raise AssertionError("missing credential must fail")
    print("education_provider_http_test: PASS")

if __name__=="__main__": main()
