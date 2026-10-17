from pathlib import Path
import py_compile

ROOT = Path(__file__).resolve().parents[1]
TARGETS = sorted((ROOT / "scripts").glob("*.py"))

def test_sync_scripts_compile():
    assert TARGETS, "scripts directory is unexpectedly empty"
    for target in TARGETS:
        py_compile.compile(str(target), doraise=True)
