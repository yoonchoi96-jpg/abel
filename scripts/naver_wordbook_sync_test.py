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
