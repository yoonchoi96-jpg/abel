from pathlib import Path

from scripts.hanping_vocab_import import merge, parse_file


def test_plain_text_and_dedupe(tmp_path: Path):
    p = tmp_path / "vocab.txt"
    p.write_text("维护\n- 发展\n维护\n", encoding="utf-8")
    rows = merge(parse_file(p))
    assert [x["hanzi"] for x in rows] == ["发展", "维护"]


def test_json_tags_and_star(tmp_path: Path):
    p = tmp_path / "hanping_test.json"
    p.write_text(
        '{"words":[{"word":"维护","starred":true,"tags":["HSK6","工作"]}]}',
        encoding="utf-8",
    )
    rows = parse_file(p)
    assert rows[0]["hanzi"] == "维护"
    assert rows[0]["starred"] is True
    assert rows[0]["tags"] == ["HSK6", "工作"]


def test_duplicate_merge_preserves_user_metadata():
    rows = merge([
        {
            "source": "hanping", "hanzi": "维护", "simplified": "维护",
            "traditional": None, "pinyin": "wei2 hu4", "starred": False,
            "tags": ["HSK6"], "note": None, "record_hash": "x"
        },
        {
            "source": "hanping", "hanzi": "维护", "simplified": "维护",
            "traditional": "維護", "pinyin": "wei2 hu4", "starred": True,
            "tags": ["工作"], "note": "公司用语", "record_hash": "y"
        },
    ])
    assert len(rows) == 1
    assert rows[0]["starred"] is True
    assert rows[0]["tags"] == ["HSK6", "工作"]
    assert rows[0]["traditional"] == "維護"
    assert rows[0]["pinyin"] == "wei2 hu4"
    assert rows[0]["note"] == "公司用语"
    assert len(rows[0]["record_hash"]) == 64



def test_homographs_remain_distinct_by_pinyin():
    rows = merge([
        {
            "source": "hanping", "hanzi": "行", "simplified": "行",
            "traditional": "行", "pinyin": "xing2", "starred": True,
            "tags": ["HSK6"], "note": "가다", "record_hash": "x",
        },
        {
            "source": "hanping", "hanzi": "行", "simplified": "行",
            "traditional": "行", "pinyin": "hang2", "starred": True,
            "tags": ["HSK6"], "note": "업종", "record_hash": "y",
        },
    ])
    assert len(rows) == 2
    assert [(r["hanzi"], r["pinyin"]) for r in rows] == [
        ("行", "hang2"),
        ("行", "xing2"),
    ]

def test_record_hash_is_deterministic(tmp_path: Path):
    p = tmp_path / "vocab.txt"
    p.write_text("维护\n", encoding="utf-8")
    first = merge(parse_file(p))[0]["record_hash"]
    second = merge(parse_file(p))[0]["record_hash"]
    assert first == second
