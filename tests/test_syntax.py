from pathlib import Path
import py_compile

ROOT = Path(__file__).resolve().parents[1]
TARGETS = sorted((ROOT / "scripts").glob("*.py"))


def test_sync_scripts_compile():
    for target in TARGETS:
        py_compile.compile(str(target), doraise=True)
