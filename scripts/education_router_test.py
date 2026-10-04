from education_router import route

def main():
    a=route("chinese_writing_correction",{"text":"我昨天去了北京","level":"HSK6"})
    assert a["primary_model"]=="gemini"
    assert a["model_chain"]==["gemini","claude","gpt"]
    assert a["cache_enabled"] is True
    b=route("current_facts_research",{"q":"HSK official update"})
    assert b["primary_model"]=="perplexity"
    assert b["cache_enabled"] is False
    c=route("vocabulary_review",{"words":["维护","贯彻"]})
    assert c["primary_model"]=="deepseek"
    assert a["source_of_truth"]=="Abel"
    assert a["cache_key"]==route("chinese_writing_correction",{"text":"我昨天去了北京","level":"HSK6"})["cache_key"]
    print("education_router_test: PASS")

if __name__=="__main__":
    main()
