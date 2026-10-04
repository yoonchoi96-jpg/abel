#!/usr/bin/env python3
import json
import tempfile
from pathlib import Path

from scripts.learning_drive_publisher import build_payload


def test_build_payload():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "index.json").write_text(
            json.dumps({"languages": ["zh-CN"]}), encoding="utf-8"
        )
        (root / "zh-CN.json").write_text(
            json.dumps({"language": "zh-CN", "stats": {"corrections": 2}}),
            encoding="utf-8",
        )
        payload = build_payload(root)
        assert payload["schema_version"] == "abel.learning.drive-payload.v2"
        assert payload["snapshots"]["zh-CN"]["stats"]["corrections"] == 2


if __name__ == "__main__":
    test_build_payload()
    print("learning_drive_publisher_test: OK")
