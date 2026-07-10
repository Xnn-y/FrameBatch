# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec for FrameBatch."""

from pathlib import Path
import sys


ROOT = Path(SPECPATH)


def optional_data(source: str, destination: str) -> list[tuple[str, str]]:
    path = ROOT / source
    return [(str(path), destination)] if path.exists() else []


datas = []
datas += optional_data("docs/RELEASE.md", "docs")
datas += optional_data("docs/FFMPEG_NOTICE.md", "docs")
datas += optional_data("tools/ffmpeg/ffmpeg.exe", "tools/ffmpeg")
datas += optional_data("tools/ffmpeg/ffprobe.exe", "tools/ffmpeg")
datas += optional_data("tools/ffmpeg/bin/ffmpeg.exe", "tools/ffmpeg/bin")
datas += optional_data("tools/ffmpeg/bin/ffprobe.exe", "tools/ffmpeg/bin")

conda_bin = Path(sys.prefix) / "Library" / "bin"
binaries = []
for dll_name in (
    "ffi.dll",
    "liblzma.dll",
    "LIBBZ2.dll",
    "libmpdec-4.dll",
    "libcrypto-3-x64.dll",
):
    dll_path = conda_bin / dll_name
    if dll_path.exists():
        binaries.append((str(dll_path), "."))


a = Analysis(
    ["framebatch/main.py"],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FrameBatch",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="FrameBatch",
)
