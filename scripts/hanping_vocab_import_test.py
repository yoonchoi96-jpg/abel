from pathlib import Path
from scripts.hanping_vocab_import import parse_file, merge

def test_plain_text_and_dedupe(tmp_path: Path):
    p = tmp_path / "vocab.txt"
    p.write_text("维护\n- 发展\n维护\n", encoding="utf-8")
    rows = merge(parse_file(p))
    assert [x["hanzi"] for x in rows] == ["发展", "维护"]

def test_json_tags_and_star():
    p = Path("/tmp/hanping_test.json")
    p.write_text(
        '{"words":[{"word":"维护","starred":true,"tags":["HSK6","工作"]}]}',
        encoding="utf-8",
    )
    try:
        rows = parse_file(p)
        assert rows[0]["hanzi"] == "维护"
        assert rows[0]["starred"] is True
        assert rows[0]["tags"] == ["HSK6", "工作"]
    finally:
        p.unlink(missing_ok=True)
