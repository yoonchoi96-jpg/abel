#!/bin/bash
set -euo pipefail

ROOT="/Users/w/abel"
PYTHON_BIN="$(command -v python3)"
PLIST="$HOME/Library/LaunchAgents/com.abel.wordbook-daemon.plist"
LOGDIR="$HOME/.naver_wordbook/logs"

mkdir -p "$HOME/Library/LaunchAgents" "$LOGDIR"

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.abel.wordbook-daemon</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON_BIN</string>
    <string>$ROOT/scripts/abel_daemon.py</string>
  </array>
  <key>WorkingDirectory</key><string>$ROOT</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ProcessType</key><string>Background</string>
  <key>StandardOutPath</key><string>$LOGDIR/abel-daemon.log</string>
  <key>StandardErrorPath</key><string>$LOGDIR/abel-daemon.err.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>NAVER_BROWSER</key><string>chrome</string>
    <key>ABEL_PYTHON</key><string>$PYTHON_BIN</string>
  </dict>
</dict>
</plist>
PLIST

plutil -lint "$PLIST"
launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl enable "gui/$(id -u)/com.abel.wordbook-daemon"
launchctl kickstart -k "gui/$(id -u)/com.abel.wordbook-daemon"

echo "Abel daemon installed and started."
launchctl print "gui/$(id -u)/com.abel.wordbook-daemon" | head -40
