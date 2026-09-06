#!/usr/bin/env bash
set -euo pipefail

# 在 macOS 上执行：./scripts/build_macos.sh
# 产物：dist/macos/校园网连接管家.app
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

cd "$PROJECT_DIR"
"$PYTHON_BIN" -m pip install -r requirements-dev.txt
APP_VERSION="$("$PYTHON_BIN" -c 'import keepalive_core; print(keepalive_core.APP_VERSION)')"
"$PYTHON_BIN" -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "校园网连接管家" \
  --icon "$PROJECT_DIR/assets/CampusNetManager.icns" \
  --osx-bundle-identifier "com.campusnettools.campusnetmanager" \
  --collect-all pystray \
  --collect-all certifi \
  --collect-submodules core \
  --collect-submodules gui \
  --distpath "$PROJECT_DIR/dist/macos" \
  --workpath "$PROJECT_DIR/build/pyinstaller-macos" \
  app_gui.py

PLIST="$PROJECT_DIR/dist/macos/校园网连接管家.app/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $APP_VERSION" "$PLIST" || \
  /usr/libexec/PlistBuddy -c "Add :CFBundleShortVersionString string $APP_VERSION" "$PLIST"
/usr/libexec/PlistBuddy -c "Set :CFBundleVersion $APP_VERSION" "$PLIST" || \
  /usr/libexec/PlistBuddy -c "Add :CFBundleVersion string $APP_VERSION" "$PLIST"
codesign --force --deep --sign - "$PROJECT_DIR/dist/macos/校园网连接管家.app"

echo "构建完成：$PROJECT_DIR/dist/macos/校园网连接管家.app"
