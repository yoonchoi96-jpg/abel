#!/usr/bin/env python3
"""Compatibility entry point.\n\nGemini is no longer called from Abel. This command only routes classified\nwords through the local Google Drive sync folder.\n"""
from pathlib import Path
import runpy

runpy.run_path(str(Path(__file__).with_name("abel_drive_bridge.py")), run_name="__main__")
