from pathlib import Path
import py_compile

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "scripts" / "naver_wordbook_sync.py"

def test_sync_script_compiles():
    py_compile.compile(str(TARGET), doraise=True)
