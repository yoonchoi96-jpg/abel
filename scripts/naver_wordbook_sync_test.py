from pathlib import Path
import sqlite3

import scripts.naver_wordbook_sync as mod


def test_upsert_reconciles_removed_naver_words_but_keeps_canonical_rows(tmp_path: Path, monkeypatch):
    db_root = tmp_path / "db"
    monkeypatch.setattr(mod, "DATA_ROOT", db_root)
    monkeypatch.setattr(mod, "DB_PATH", db_root / "naver_wordbook.sqlite3")

    wordbook = {
        "naver_id": "wb-1",
        "name": "내가 찾은 단어",
        "source_url": "https://example.test/wb-1",
    }
    first_cards = [
        {
            "word": "维护",
            "meaning": "유지하다",
            "pronunciation": "wei2 hu4",
            "part_of_speech": "동사",
            "example": "",
            "wordbook_id": "wb-1",
            "wordbook": "내가 찾은 단어",
            "source_url": wordbook["source_url"],
        },
        {
            "word": "学习",
            "meaning": "공부하다",
            "pronunciation": "xue2 xi2",
            "part_of_speech": "동사",
            "example": "",
            "wordbook_id": "wb-1",
            "wordbook": "내가 찾은 단어",
            "source_url": wordbook["source_url"],
        },
    ]
    mod.upsert_db(first_cards, [wordbook])

    second_cards = [first_cards[0]]
    mod.upsert_db(second_cards, [wordbook])

    with sqlite3.connect(mod.DB_PATH) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM wordbook_words"
        ).fetchone()[0] == 1
        assert db.execute(
            """SELECT w.word
               FROM wordbook_words ww
               JOIN words w ON w.id=ww.word_id"""
        ).fetchone()[0] == "维护"
        assert db.execute(
            "SELECT COUNT(*) FROM words"
        ).fetchone()[0] == 2


def test_upsert_empty_wordbook_removes_all_memberships_only(tmp_path: Path, monkeypatch):
    db_root = tmp_path / "db"
    monkeypatch.setattr(mod, "DATA_ROOT", db_root)
    monkeypatch.setattr(mod, "DB_PATH", db_root / "naver_wordbook.sqlite3")

    wordbook = {
        "naver_id": "wb-empty",
        "name": "내가 찾은 단어",
        "source_url": "https://example.test/wb-empty",
    }
    card = {
        "word": "维护",
        "meaning": "유지하다",
        "pronunciation": "wei2 hu4",
        "part_of_speech": "동사",
        "example": "",
        "wordbook_id": "wb-empty",
        "wordbook": "내가 찾은 단어",
        "source_url": wordbook["source_url"],
    }
    mod.upsert_db([card], [wordbook])
    mod.upsert_db([], [wordbook])

    with sqlite3.connect(mod.DB_PATH) as db:
        assert db.execute("SELECT COUNT(*) FROM wordbook_words").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM words").fetchone()[0] == 1


def test_upsert_preserves_hanping_membership_when_naver_removes_word(tmp_path: Path, monkeypatch):
    db_root = tmp_path / "db"
    monkeypatch.setattr(mod, "DATA_ROOT", db_root)
    monkeypatch.setattr(mod, "DB_PATH", db_root / "naver_wordbook.sqlite3")

    naver = {
        "naver_id": "wb-1",
        "name": "내가 찾은 단어",
        "source_url": "https://example.test/wb-1",
    }
    hanping = {
        "naver_id": None,
        "name": "Hanping",
        "source_url": "hanping",
    }
    card = {
        "word": "维护",
        "meaning": "유지하다",
        "pronunciation": "wei2 hu4",
        "part_of_speech": "동사",
        "example": "",
        "wordbook_id": "wb-1",
        "wordbook": "내가 찾은 단어",
        "source_url": naver["source_url"],
    }

    mod.upsert_db([card], [naver])
    mod.upsert_db(
        [{
            **card,
            "wordbook_id": "",
            "wordbook": "Hanping",
        }],
        [hanping],
    )
    mod.upsert_db([], [naver])

    with sqlite3.connect(mod.DB_PATH) as db:
        assert db.execute("SELECT COUNT(*) FROM words").fetchone()[0] == 1
        assert db.execute(
            """SELECT COUNT(*)
               FROM wordbook_words ww
               JOIN wordbooks wb ON wb.id=ww.wordbook_id
               WHERE wb.name='Hanping'"""
        ).fetchone()[0] == 1
        assert db.execute(
            """SELECT COUNT(*)
               FROM wordbook_words ww
               JOIN wordbooks wb ON wb.id=ww.wordbook_id
               WHERE wb.name='내가 찾은 단어'"""
        ).fetchone()[0] == 0


def test_naver_and_hanping_share_one_canonical_word_and_independent_memberships(
    tmp_path: Path, monkeypatch
):
    db_root = tmp_path / "db"
    db_path = db_root / "abel.sqlite3"

    monkeypatch.setattr(mod, "DATA_ROOT", db_root)
    monkeypatch.setattr(mod, "DB_PATH", db_path)

    import scripts.hanping_db_sync as hanping_mod
    import scripts.abel_wordbook_db as db_layer

    monkeypatch.setattr(db_layer, "DB_PATH", db_path)
    monkeypatch.setattr(hanping_mod, "DB_PATH", db_path)

    naver = {
        "naver_id": "wb-shared",
        "name": "내가 찾은 단어",
        "source_url": "https://example.test/wb-shared",
    }
    naver_card = {
        "word": "维护",
        "meaning": "유지하다",
        "pronunciation": "wei2 hu4",
        "part_of_speech": "동사",
        "example": "",
        "wordbook_id": "wb-shared",
        "wordbook": "내가 찾은 단어",
        "source_url": naver["source_url"],
    }

    hanping_mod.init_db()
    mod.upsert_db([naver_card], [naver])

    import json
    hanping_input = tmp_path / "hanping.json"
    hanping_input.write_text(
        json.dumps({
            "schema_version": 1,
            "source": "hanping",
            "words": [{
                "source": "hanping",
                "hanzi": "维护",
                "simplified": "维护",
                "traditional": "維護",
                "pinyin": "wei2 hu4",
                "starred": True,
                "tags": ["HSK6"],
                "note": "같은 단어",
                "record_hash": "shared-1",
            }],
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    assert hanping_mod.sync(hanping_input) == {
        "inserted": 0,
        "updated": 1,
        "total": 1,
    }

    with sqlite3.connect(db_path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM words WHERE word='维护'"
        ).fetchone()[0] == 1
        word_id = db.execute(
            "SELECT id FROM words WHERE word='维护' AND pronunciation='wei2 hu4'"
        ).fetchone()[0]

        assert db.execute(
            """SELECT COUNT(*)
               FROM wordbook_words ww
               JOIN wordbooks wb ON wb.id=ww.wordbook_id
               WHERE wb.name='내가 찾은 단어' AND ww.word_id=?""",
            (word_id,),
        ).fetchone()[0] == 1
        assert db.execute(
            """SELECT COUNT(*)
               FROM wordbook_words ww
               JOIN wordbooks wb ON wb.id=ww.wordbook_id
               WHERE wb.name='Hanping' AND ww.word_id=?""",
            (word_id,),
        ).fetchone()[0] == 1

    mod.upsert_db([], [naver])

    with sqlite3.connect(db_path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM words WHERE id=?", (word_id,)
        ).fetchone()[0] == 1
        assert db.execute(
            """SELECT COUNT(*)
               FROM wordbook_words ww
               JOIN wordbooks wb ON wb.id=ww.wordbook_id
               WHERE wb.name='내가 찾은 단어' AND ww.word_id=?""",
            (word_id,),
        ).fetchone()[0] == 0
        assert db.execute(
            """SELECT COUNT(*)
               FROM wordbook_words ww
               JOIN wordbooks wb ON wb.id=ww.wordbook_id
               WHERE wb.name='Hanping' AND ww.word_id=?""",
            (word_id,),
        ).fetchone()[0] == 1

    hanping_empty = tmp_path / "hanping-empty.json"
    hanping_empty.write_text(
        json.dumps(
            {"schema_version": 1, "source": "hanping", "words": []},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    assert hanping_mod.sync(hanping_empty) == {
        "inserted": 0,
        "updated": 0,
        "total": 0,
    }

    with sqlite3.connect(db_path) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM words WHERE id=?", (word_id,)
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT COUNT(*) FROM wordbook_words WHERE word_id=?",
            (word_id,),
        ).fetchone()[0] == 0


def test_naver_and_hanping_keep_cross_source_homographs_separate(
    tmp_path: Path, monkeypatch
):
    db_root = tmp_path / "db"
    db_path = db_root / "abel.sqlite3"
    monkeypatch.setattr(mod, "DATA_ROOT", db_root)
    monkeypatch.setattr(mod, "DB_PATH", db_path)

    import scripts.hanping_db_sync as hanping_mod
    import scripts.abel_wordbook_db as db_layer
    monkeypatch.setattr(db_layer, "DB_PATH", db_path)
    monkeypatch.setattr(hanping_mod, "DB_PATH", db_path)

    hanping_mod.init_db()
    mod.upsert_db(
        [
            {
                "word": "行",
                "meaning": "行走",
                "pronunciation": "xing2",
                "wordbook_id": "wb-x",
                "wordbook": "내 단어",
                "source_url": "",
            },
            {
                "word": "行",
                "meaning": "은행",
                "pronunciation": "hang2",
                "wordbook_id": "wb-h",
                "wordbook": "내 단어",
                "source_url": "",
            },
        ],
        [
            {"naver_id": "wb-x", "name": "내 단어", "source_url": ""},
            {"naver_id": "wb-h", "name": "내 단어", "source_url": ""},
        ],
    )

    payload = tmp_path / "hanping.json"
    import json
    payload.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source": "hanping",
                "words": [
                    {
                        "hanzi": "行",
                        "pinyin": "hang2",
                        "traditional": "行",
                        "starred": True,
                        "tags": [],
                        "note": "",
                        "record_hash": "homograph-hang2",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    stats = hanping_mod.sync(payload)
    assert stats["inserted"] == 0
    assert stats["updated"] == 1

    with sqlite3.connect(db_path) as db:
        rows = db.execute(
            "SELECT id, pronunciation, meaning FROM words WHERE word='行' ORDER BY id"
        ).fetchall()
        assert {(pron, meaning) for _, pron, meaning in rows} == {
            ("xing2", "行走"),
            ("hang2", "银行"),
        }
        hang_id = next(row[0] for row in rows if row[1] == "hang2")
        assert db.execute(
            "SELECT COUNT(*) FROM hanping_vocab WHERE word_id=?",
            (hang_id,),
        ).fetchone()[0] == 1
