#!/bin/bash
set -e

echo "Setting up Gearbox..."

# Detect current project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_BIN="$PROJECT_DIR/venv/bin/python3"
LAUNCH_DIR="$HOME/Library/LaunchAgents"

mkdir -p "$LAUNCH_DIR"

DAEMON_PLIST="$LAUNCH_DIR/com.gearbox.daemon.plist"
UI_PLIST="$LAUNCH_DIR/com.gearbox.ui.plist"

echo "Creating Daemon Plist -> $DAEMON_PLIST"
cat > "$DAEMON_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.gearbox.daemon</string>
    <key>ProgramArguments</key>
    <array>
        <string>$VENV_BIN</string>
        <string>$PROJECT_DIR/daemon.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardErrorPath</key>
    <string>$HOME/.gearbox/daemon-error.log</string>
    <key>StandardOutPath</key>
    <string>$HOME/.gearbox/daemon.log</string>
</dict>
</plist>
EOF

echo "Creating UI Plist -> $UI_PLIST"
cat > "$UI_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.gearbox.ui</string>
    <key>ProgramArguments</key>
    <array>
        <string>$VENV_BIN</string>
        <string>$PROJECT_DIR/ui.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardErrorPath</key>
    <string>$HOME/.gearbox/ui-error.log</string>
    <key>StandardOutPath</key>
    <string>$HOME/.gearbox/ui.log</string>
</dict>
</plist>
EOF

echo "Loading LaunchAgents..."
launchctl unload "$DAEMON_PLIST" 2>/dev/null || true
launchctl unload "$UI_PLIST" 2>/dev/null || true

launchctl load "$DAEMON_PLIST"
launchctl load "$UI_PLIST"

echo "Gearbox has been successfully installed and started!"
echo ""
echo "To manage tasks from the CLI easily, add this alias to your shell profile (~/.zshrc or ~/.bash_profile):"
echo "alias gearbox='$VENV_BIN $PROJECT_DIR/cli.py'"
echo ""
echo "Then start using it:"
echo "gearbox add dummy '* * * * *' 'echo \"Hello World!\"'"
