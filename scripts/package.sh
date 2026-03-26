#!/bin/bash
set -e

# Gearbox Packaging Script
# This script creates a distributable ZIP of the Gearbox.app for Homebrew Cask.

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$PROJECT_DIR/dist"
APP_NAME="Gearbox"
APP_BUNDLE="$BUILD_DIR/$APP_NAME.app"

echo "🧹 Cleaning previous builds..."
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

echo "🏗 Building Swift UI..."
cd "$PROJECT_DIR/GearboxUI"
swift build -c release

echo "📦 Creating App Bundle..."
mkdir -p "$APP_BUNDLE/Contents/MacOS"
mkdir -p "$APP_BUNDLE/Contents/Resources"

# Copy binary
cp "$PROJECT_DIR/GearboxUI/.build/release/GearboxUI" "$APP_BUNDLE/Contents/MacOS/"

# Generate Icon
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

    iconutil -c icns "$ICONSET_DIR" -o "$APP_BUNDLE/Contents/Resources/AppIcon.icns"
    rm -rf "$ICONSET_DIR"
fi

# Info.plist
cat > "$APP_BUNDLE/Contents/Info.plist" <<EOF
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
    <string>1.0.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSUIElement</key>
    <true/>
</dict>
</plist>
EOF

# Sign
codesign --force --deep -s - "$APP_BUNDLE"

echo "🗜 Compressing into ZIP..."
cd "$BUILD_DIR"
zip -r "gearbox-1.0.0.zip" "$APP_NAME.app"

echo "✅ Packaging complete: $BUILD_DIR/gearbox-1.0.0.zip"
sha256sum "gearbox-1.0.0.zip" || shasum -a 256 "gearbox-1.0.0.zip"
