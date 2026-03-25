#!/bin/bash
set -e

echo "Building GearboxUI Swift App..."
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR/GearboxUI"

swift build -c release

mkdir -p build/GearboxUI.app/Contents/MacOS
cp .build/release/GearboxUI build/GearboxUI.app/Contents/MacOS/

echo "Generating AppIcon..."
mkdir -p build/GearboxUI.app/Contents/Resources
ICONSET_DIR="build/AppIcon.iconset"
mkdir -p "$ICONSET_DIR"

if [ -f "Resources/AppIcon.png" ]; then
    sips -z 16 16     Resources/AppIcon.png --out "$ICONSET_DIR/icon_16x16.png" > /dev/null
    sips -z 32 32     Resources/AppIcon.png --out "$ICONSET_DIR/icon_16x16@2x.png" > /dev/null
    sips -z 32 32     Resources/AppIcon.png --out "$ICONSET_DIR/icon_32x32.png" > /dev/null
    sips -z 64 64     Resources/AppIcon.png --out "$ICONSET_DIR/icon_32x32@2x.png" > /dev/null
    sips -z 128 128   Resources/AppIcon.png --out "$ICONSET_DIR/icon_128x128.png" > /dev/null
    sips -z 256 256   Resources/AppIcon.png --out "$ICONSET_DIR/icon_128x128@2x.png" > /dev/null
    sips -z 256 256   Resources/AppIcon.png --out "$ICONSET_DIR/icon_256x256.png" > /dev/null
    sips -z 512 512   Resources/AppIcon.png --out "$ICONSET_DIR/icon_256x256@2x.png" > /dev/null
    sips -z 512 512   Resources/AppIcon.png --out "$ICONSET_DIR/icon_512x512.png" > /dev/null
    sips -z 1024 1024 Resources/AppIcon.png --out "$ICONSET_DIR/icon_512x512@2x.png" > /dev/null

    iconutil -c icns "$ICONSET_DIR" -o build/GearboxUI.app/Contents/Resources/AppIcon.icns
    rm -rf "$ICONSET_DIR"
else
    echo "Warning: Resources/AppIcon.png not found. AppIcon will not be generated."
fi

cat > build/GearboxUI.app/Contents/Info.plist <<EOF
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
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>LSUIElement</key>
    <true/>
</dict>
</plist>
EOF

echo "Applying Ad-Hoc Code Signature to bypass AMFI..."
codesign --force --deep -s - "build/GearboxUI.app"

echo "Updating LaunchAgent for UI to use Native Swift App..."
UI_PLIST="$HOME/Library/LaunchAgents/com.gearbox.ui.plist"

launchctl unload "$UI_PLIST" 2>/dev/null || true

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

launchctl load "$UI_PLIST"
echo "Done! The Native macOS Menu Bar UI is now running!"
