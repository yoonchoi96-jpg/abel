import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def rows(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def test_hsk_level6_has_1140_rows():
    data = rows(ROOT / "data/hsk30_level6_1140.csv")
    assert len(data) == 1140
    assert all(r["meaning_ko"].strip() for r in data)

def test_hsk_level79_has_5600_rows():
    data = rows(ROOT / "data/hsk30_level7_9_5600.csv")
    assert len(data) == 5600
    assert all(r["word"].strip() and r["pinyin"].strip() for r in data)
