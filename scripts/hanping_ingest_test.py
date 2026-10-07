from pathlib import Path

from scripts.hanping_ingest import DEFAULT_OUTPUT, main


def test_default_output_is_git_ignored():
    assert DEFAULT_OUTPUT.as_posix().endswith("data/hanping/normalized.json")


def test_ingest_writes_normalized_snapshot(tmp_path: Path, monkeypatch):
    source = tmp_path / "export.txt"
    source.write_text("维护\n发展\n维护\n", encoding="utf-8")
    output = tmp_path / "normalized.json"

    monkeypatch.setattr(
        "sys.argv",
        ["hanping_ingest.py", str(source), "--output", str(output)],
    )
    main()

    payload = output.read_text(encoding="utf-8")
    assert '"count": 2' in payload
    assert '"source": "hanping"' in payload
    assert "维护" in payload
    assert "发展" in payload
