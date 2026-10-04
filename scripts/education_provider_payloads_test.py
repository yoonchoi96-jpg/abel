import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from education_provider_payloads import build

def main():
    assert build("gpt",{"text":"x"})["store"] is False
    assert build("claude",{"text":"x","system":"s"})["system"]=="s"
    assert build("deepseek",{"text":"x"})["temperature"]==0
    assert build("perplexity",{"text":"x"})["messages"]
    assert build("gemini",{"text":"x"})["contents"][0]["parts"][0]["text"]=="x"
    print("education_provider_payloads_test: PASS")

if __name__=="__main__": main()
