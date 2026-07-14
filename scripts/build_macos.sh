#!/usr/bin/env bash
set -euo pipefail

CLEAN=0
if [[ "${1:-}" == "--clean" || "${1:-}" == "-c" ]]; then
  CLEAN=1
fi

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPEC_PATH="$PROJECT_ROOT/FrameBatch.spec"
DIST_DIR="$PROJECT_ROOT/dist"
BUILD_DIR="$PROJECT_ROOT/build"
RELEASE_DIR="$DIST_DIR/FrameBatch"
ROOT_APP_PATH="$DIST_DIR/FrameBatch.app"
NESTED_APP_PATH="$RELEASE_DIR/FrameBatch.app"

cd "$PROJECT_ROOT"

VERSION="$(python3 -c 'import pathlib, tomllib; print(tomllib.loads(pathlib.Path("pyproject.toml").read_text(encoding="utf-8"))["project"]["version"])')"
ARCH="$(uname -m)"
case "$ARCH" in
  arm64)
    PLATFORM_TAG="macos-arm64"
    ;;
  x86_64)
    PLATFORM_TAG="macos-x64"
    ;;
  *)
    PLATFORM_TAG="macos-$ARCH"
    ;;
esac

ZIP_NAME="FrameBatch-v${VERSION}-${PLATFORM_TAG}.zip"
ZIP_PATH="$DIST_DIR/$ZIP_NAME"
PACKAGE_DIR="$DIST_DIR/FrameBatch-v${VERSION}-${PLATFORM_TAG}"

if [[ ! -f "$SPEC_PATH" ]]; then
  echo "Missing PyInstaller spec: $SPEC_PATH" >&2
  exit 1
fi

if [[ "$CLEAN" == "1" ]]; then
  rm -rf "$BUILD_DIR" "$RELEASE_DIR" "$ROOT_APP_PATH" "$PACKAGE_DIR" "$ZIP_PATH"
fi

python3 -m PyInstaller --version >/dev/null 2>&1 || {
  echo 'PyInstaller is not installed. Run: python3 -m pip install -e ".[build]"' >&2
  exit 1
}

echo "Building FrameBatch for $PLATFORM_TAG..."
python3 -m PyInstaller --noconfirm "$SPEC_PATH"

if [[ -d "$ROOT_APP_PATH" ]]; then
  APP_PATH="$ROOT_APP_PATH"
elif [[ -d "$NESTED_APP_PATH" ]]; then
  APP_PATH="$NESTED_APP_PATH"
else
  echo "Build finished, but FrameBatch.app was not found in $DIST_DIR" >&2
  exit 1
fi

rm -rf "$PACKAGE_DIR"
mkdir -p "$PACKAGE_DIR"
ditto "$APP_PATH" "$PACKAGE_DIR/FrameBatch.app"

DOCS_RELEASE_DIR="$PACKAGE_DIR/docs"
mkdir -p "$DOCS_RELEASE_DIR"
for doc_name in RELEASE.md FFMPEG_NOTICE.md MACOS_ADAPTATION_PLAN.md; do
  if [[ -f "$PROJECT_ROOT/docs/$doc_name" ]]; then
    cp "$PROJECT_ROOT/docs/$doc_name" "$DOCS_RELEASE_DIR/"
  fi
done

rm -f "$ZIP_PATH"
mkdir -p "$DIST_DIR"
ditto -c -k --sequesterRsrc --keepParent "$PACKAGE_DIR" "$ZIP_PATH"

if [[ ! -f "$ZIP_PATH" ]]; then
  echo "Failed to create zip archive." >&2
  exit 1
fi

ZIP_SIZE="$(python3 -c 'import pathlib, sys; print(round(pathlib.Path(sys.argv[1]).stat().st_size / 1024 / 1024, 1))' "$ZIP_PATH")"
echo ""
echo "=============================================================================="
echo "  Build completed successfully!"
echo ""
echo "  Release app   : $PACKAGE_DIR/FrameBatch.app"
echo "  Distributable : $ZIP_PATH (${ZIP_SIZE} MB)"
echo ""
echo "  Usage:"
echo "    1. Send $ZIP_NAME to macOS users"
echo "    2. Users unzip and open FrameBatch.app"
echo "    3. If macOS blocks unsigned apps, use signed/notarized builds for public release"
echo "=============================================================================="
