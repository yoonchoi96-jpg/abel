import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from education_provider_normalizer import normalize

def main():
    assert normalize("gpt",{"output_text":"a"})["text"]=="a"
    assert normalize("claude",{"content":[{"text":"b"}]})["text"]=="b"
    assert normalize("deepseek",{"choices":[{"message":{"content":"c"}}]})["text"]=="c"
    assert normalize("perplexity",{"choices":[{"message":{"content":"d"}}]})["text"]=="d"
    assert normalize("gemini",{"candidates":[{"content":{"parts":[{"text":"e"}]}}]})["text"]=="e"
    print("education_provider_normalizer_test: PASS")
if __name__=="__main__": main()
