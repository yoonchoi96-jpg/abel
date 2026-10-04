#!/usr/bin/env python3
import json, tempfile
from pathlib import Path
from scripts.abel_learning_drive_sync import sync

def test_sync():
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp)
        src=root/"snapshots"; dst=root/"drive"
        src.mkdir()
        (src/"index.json").write_text(json.dumps({"languages":["zh-CN"]}), encoding="utf-8")
        (src/"zh-CN.json").write_text(json.dumps({"language":"zh-CN"}), encoding="utf-8")
        (src/"zh-CN.md").write_text("# Chinese\n", encoding="utf-8")
        result=sync(src,dst)
        assert result["snapshot_count"] == 1
        assert (dst/"zh-CN.json").exists()
        assert (dst/"zh-CN.md").exists()
        assert json.loads((dst/"_ABEL_SYNC_STATUS.json").read_text())["source"] == "Abel"

if __name__=="__main__":
    test_sync()
    print("abel_learning_drive_sync_test: OK")
