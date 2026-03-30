#!/bin/bash
set -e

VERSION="1.0.6"

echo "Setting up Gearbox..."

# Detect current project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/venv"
VENV_BIN="$VENV_DIR/bin/python3"

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

echo "Installing dependencies..."
"$VENV_BIN" -m pip install --upgrade pip
"$VENV_BIN" -m pip install -r "$PROJECT_DIR/requirements.txt"

LAUNCH_DIR="$HOME/Library/LaunchAgents"
LAUNCH_DOMAIN="gui/$(id -u)"

mkdir -p "$LAUNCH_DIR"

DAEMON_PLIST="$LAUNCH_DIR/com.gearbox.daemon.plist"
UI_PLIST="$LAUNCH_DIR/com.gearbox.ui.plist"

echo "Building Native Swift UI App..."
cd "$PROJECT_DIR/GearboxUI"
swift build -c release

mkdir -p "$PROJECT_DIR/GearboxUI/build/GearboxUI.app/Contents/MacOS"
cp "$PROJECT_DIR/GearboxUI/.build/release/GearboxUI" "$PROJECT_DIR/GearboxUI/build/GearboxUI.app/Contents/MacOS/"

# Generate AppIcon
mkdir -p "$PROJECT_DIR/GearboxUI/build/AppIcon.iconset"
ICONSET_DIR="$PROJECT_DIR/GearboxUI/build/AppIcon.iconset"
if [ -f "$PROJECT_DIR/GearboxUI/Resources/AppIcon.png" ]; then
    sips -z 16 16     "$PROJECT_DIR/GearboxUI/Resources/AppIcon.png" --out "$ICONSET_DIR/icon_16x16.png" > /dev/null
    sips -z 32 32     "$PROJECT_DIR/GearboxUI/Resources/AppIcon.png" --out "$ICONSET_DIR/icon_16x16@2x.png" > /dev/null
    sips -z 32 32     "$PROJECT_DIR/GearboxUI/Resources/AppIcon.png" --out "$ICONSET_DIR/icon_32x32.png" > /dev/null
    sips -z 64 64     "$PROJECT_DIR/GearboxUI/Resources/AppIcon.png" --out "$ICONSET_DIR/icon_32x32@2x.png" > /dev/null
    sips -z 128 128   "$PROJECT_DIR/GearboxUI/Resources/AppIcon.png" --out "$ICONSET_DIR/icon_128x128.png" > /dev/null
    sips -z 256 256   "$PROJECT_DIR/GearboxUI/Resources/AppIcon.png" --out "$ICONSET_DIR/icon_128x128@2x.png" > /dev/null
    sips -z 256 256   "$PROJECT_DIR/GearboxUI/Resources/AppIcon.png" --out "$ICONSET_DIR/icon_256x256.png" > /dev/null
    sips -z 512 512   "$PROJECT_DIR/GearboxUI/Resources/AppIcon.png" --out "$ICONSET_DIR/icon_256x256@2x.png" > /dev/null
    sips -z 512 512   "$PROJECT_DIR/GearboxUI/Resources/AppIcon.png" --out "$ICONSET_DIR/icon_512x512.png" > /dev/null
    sips -z 1024 1024 "$PROJECT_DIR/GearboxUI/Resources/AppIcon.png" --out "$ICONSET_DIR/icon_512x512@2x.png" > /dev/null

    iconutil -c icns "$ICONSET_DIR" -o "$PROJECT_DIR/GearboxUI/build/GearboxUI.app/Contents/Resources/AppIcon.icns"
    rm -rf "$ICONSET_DIR"
fi

cat > "$PROJECT_DIR/GearboxUI/build/GearboxUI.app/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>GearboxUI</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleIdentifier</key>
    <string>com.gearbox.ui</string>
    <key>CFBundleName</key>
    <string>Gearbox</string>
    <key>CFBundleShortVersionString</key>
    <string>$VERSION</string>
    <key>CFBundleVersion</key>
    <string>5</string>
    <key>LSUIElement</key>
    <true/>
</dict>
</plist>
EOF

codesign --force --deep -s - "$PROJECT_DIR/GearboxUI/build/GearboxUI.app"

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
        <string>$PROJECT_DIR/GearboxUI/build/GearboxUI.app/Contents/MacOS/GearboxUI</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardErrorPath</key>
    <string>$HOME/.gearbox/ui-error.log</string>
    <key>StandardOutPath</key>
    <string>$HOME/.gearbox/ui.log</string>
</dict>
</plist>
EOF

echo "Loading LaunchAgents..."
launchctl bootout "$LAUNCH_DOMAIN" "$DAEMON_PLIST" 2>/dev/null || true
launchctl bootout "$LAUNCH_DOMAIN" "$UI_PLIST" 2>/dev/null || true
rm -f "$DAEMON_PLIST"

launchctl bootstrap "$LAUNCH_DOMAIN" "$UI_PLIST"

echo "Gearbox has been successfully installed and started!"
echo ""
echo "To manage tasks from the CLI easily, add this alias to your shell profile (~/.zshrc or ~/.bash_profile):"
echo "alias gearbox='$VENV_BIN $PROJECT_DIR/cli.py'"
echo ""
echo "Then start using it:"
echo "gearbox add dummy '* * * * *' 'echo \"Hello World!\"'"
