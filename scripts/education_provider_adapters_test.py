import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from education_provider_adapters import configured, contract, make_stub

def main():
    env={"GEMINI_API_KEY":"x"}
    assert configured("gemini",env)
    assert not configured("deepseek",env)
    c=contract("gemini",env=env)
    assert c["configured"] is True and c["api_call_allowed"] is False
    r=make_stub("gemini")({"text":"hello"})
    assert r["status"]=="dry_run"
    print("education_provider_adapters_test: PASS")

if __name__=="__main__":
    main()
