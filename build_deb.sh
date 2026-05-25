#!/bin/bash
# Build minlai_<version>_all.deb
# Usage: ./build_deb.sh [version]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPT_VERSION="$(cat "$SCRIPT_DIR/VERSION" 2>/dev/null | tr -d '[:space:]')"
VERSION="${1:-${SCRIPT_VERSION:-2.3.7}}"
PKG_NAME="minlai"
BUILD_DIR="$(mktemp -d)"

echo "Building ${PKG_NAME}_${VERSION}_all.deb …"

# ── Prepare package tree ──────────────────────────────────────────────────────
PKG_ROOT="$BUILD_DIR/${PKG_NAME}_${VERSION}_all"

# Copy packaging skeleton (DEBIAN/, usr/)
cp -r "$SCRIPT_DIR/packaging/." "$PKG_ROOT/"

# Remove old orbit binary if present (leftover from old packaging skeleton)
rm -f "$PKG_ROOT/usr/bin/orbit"
rm -f "$PKG_ROOT/usr/share/applications/orbit.desktop"

# Stamp version into control file
sed -i "s/^Version:.*/Version: $VERSION/" "$PKG_ROOT/DEBIAN/control"

# ── Install Python source files ───────────────────────────────────────────────
DEST="$PKG_ROOT/usr/lib/minlai"
mkdir -p "$DEST"
for py in main.py capture.py ai.py overlay.py tray.py settings_dialog.py config.py themes.py voice.py logger.py version.py; do
    install -m 644 "$SCRIPT_DIR/$py" "$DEST/"
done
install -m 644 "$SCRIPT_DIR/VERSION" "$DEST/"

# ── Install icon ──────────────────────────────────────────────────────────────
mkdir -p "$PKG_ROOT/usr/share/icons/hicolor/scalable/apps"
install -m 644 "$SCRIPT_DIR/minlai.svg" \
    "$PKG_ROOT/usr/share/icons/hicolor/scalable/apps/minlai.svg"

# ── Set permissions ───────────────────────────────────────────────────────────
chmod 755 "$PKG_ROOT/DEBIAN/postinst"
chmod 755 "$PKG_ROOT/DEBIAN/prerm"
chmod 755 "$PKG_ROOT/DEBIAN/postrm"
chmod 755 "$PKG_ROOT/usr/bin/minlai"

# ── Compute installed size (kB) ───────────────────────────────────────────────
INSTALLED_KB=$(du -sk "$PKG_ROOT" | awk '{print $1}')
echo "Installed-Size: $INSTALLED_KB" >> "$PKG_ROOT/DEBIAN/control"

# ── Build .deb ────────────────────────────────────────────────────────────────
OUTPUT="$SCRIPT_DIR/${PKG_NAME}_${VERSION}_all.deb"
dpkg-deb --build --root-owner-group "$PKG_ROOT" "$OUTPUT"

# Cleanup
rm -rf "$BUILD_DIR"

echo ""
echo "Done: $OUTPUT"
echo ""
echo "Install with:"
echo "  sudo apt install ./${PKG_NAME}_${VERSION}_all.deb"
echo ""
echo "Then set your API key:"
echo "  export ANTHROPIC_API_KEY=sk-ant-..."
echo "  minlai                # starts tray icon"
echo ""
echo "To launch at login: open the tray menu → Settings → check 'Launch at login'"
