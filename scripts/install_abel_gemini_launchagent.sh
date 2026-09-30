#!/bin/bash
set -euo pipefail
ROOT="/Users/w/abel"
PYTHON_BIN="$(command -v python3)"
PLIST="$HOME/Library/LaunchAgents/com.abel.gemini-education.plist"
LOG_DIR="$HOME/.naver_wordbook/logs"
mkdir -p "$HOME/Library/LaunchAgents" "$LOG_DIR"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>com.abel.gemini-education</string>
<key>ProgramArguments</key><array><string>$PYTHON_BIN</string><string>$ROOT/scripts/abel_drive_bridge.py</string></array>
<key>WorkingDirectory</key><string>$ROOT</string>
<key>StartInterval</key><integer>300</integer>
<key>RunAtLoad</key><true/>
<key>StandardOutPath</key><string>$LOG_DIR/abel-gemini.log</string>
<key>StandardErrorPath</key><string>$LOG_DIR/abel-gemini.err.log</string>
</dict></plist>
EOF
launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl enable "gui/$(id -u)/com.abel.gemini-education"
launchctl kickstart -k "gui/$(id -u)/com.abel.gemini-education"
echo "Installed: $PLIST"
