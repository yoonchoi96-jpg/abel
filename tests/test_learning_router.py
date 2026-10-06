from learning_router import resolve_learning_route

def test_chinese_listening():
    route = resolve_learning_route(language="zh-CN", skill="listening", level="HSK6")
    assert route.parts == ("Chinese", "Listening", "HSK6")

def test_aliases():
    route = resolve_learning_route(language="Spanish", skill="listen", level="B2")
    assert route.parts == ("Spanish", "Listening", "B2")

def test_unknown_language_rejected():
    try:
        resolve_learning_route(language="de", skill="listening", level="B2")
    except ValueError:
        return
    raise AssertionError

def test_unsafe_level_rejected():
    try:
        resolve_learning_route(language="fr", skill="writing", level="../secret")
    except ValueError:
        return
    raise AssertionError
