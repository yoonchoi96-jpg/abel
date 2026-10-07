from pathlib import Path
import py_compile

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "scripts" / "naver_wordbook_sync.py"


def test_sync_scripts_compile():
    py_compile.compile(str(TARGET), doraise=True)
