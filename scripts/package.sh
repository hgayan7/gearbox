#!/bin/bash
set -e

# Gearbox Packaging Script (Standalone Cask Version)
# This script creates a truly self-contained Gearbox.app containing:
# 1. The Swift UI binary
# 2. A bundled Python 3.11 virtualenv with all dependencies
# 3. The Python daemon and CLI source files

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$PROJECT_DIR/dist"
APP_NAME="Gearbox"
VERSION="1.0.6"
APP_BUNDLE="$BUILD_DIR/$APP_NAME.app"
CONTENTS="$APP_BUNDLE/Contents"
RESOURCES="$CONTENTS/Resources"
MACOS="$CONTENTS/MacOS"

echo "🧹 Cleaning previous builds..."
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

echo "🏗 Building Swift UI..."
cd "$PROJECT_DIR/GearboxUI"
swift build -c release

echo "📦 Creating App Bundle Structure..."
mkdir -p "$MACOS"
mkdir -p "$RESOURCES/python"

# Copy Swift binary
cp "$PROJECT_DIR/GearboxUI/.build/release/GearboxUI" "$MACOS/"

# Copy Python Source
echo "🐍 Copying Python source files..."
cp "$PROJECT_DIR/cli.py" "$RESOURCES/python/"
cp "$PROJECT_DIR/daemon.py" "$RESOURCES/python/"
cp -R "$PROJECT_DIR/core" "$RESOURCES/python/"

echo "⚙️ Creating Embedded Python Virtualenv..."
# Use python3.11 from the system/homebrew to create the initial venv
python3.11 -m venv "$RESOURCES/venv"

# Install dependencies into the embedded venv
echo "pip: Installing dependencies into bundle..."
"$RESOURCES/venv/bin/pip" install --upgrade pip
"$RESOURCES/venv/bin/pip" install click apscheduler cron-descriptor pytz six tzlocal

echo "📜 Creating CLI Shim..."
cp "$PROJECT_DIR/scripts/gearbox-shim.sh" "$MACOS/gearbox"
chmod +x "$MACOS/gearbox"

echo "🎨 Generating App Icon..."
ICONSET_DIR="$BUILD_DIR/AppIcon.iconset"
mkdir -p "$ICONSET_DIR"
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

    iconutil -c icns "$ICONSET_DIR" -o "$RESOURCES/AppIcon.icns"
    rm -rf "$ICONSET_DIR"
fi

echo "📝 Generating Info.plist..."
cat > "$CONTENTS/Info.plist" <<EOF
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
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>$VERSION</string>
    <key>CFBundleVersion</key>
    <string>5</string>
    <key>LSUIElement</key>
    <true/>
</dict>
</plist>
EOF

echo "🖋 Signing App Bundle..."
# Deep sign everything including the embedded venv
codesign --force --deep -s - "$APP_BUNDLE"

echo "🗜 Compressing into ZIP..."
cd "$BUILD_DIR"
zip -r "gearbox-$VERSION.zip" "$APP_NAME.app"

echo "✅ Standalone Packaging complete: $BUILD_DIR/gearbox-$VERSION.zip"
shasum -a 256 "gearbox-$VERSION.zip"
