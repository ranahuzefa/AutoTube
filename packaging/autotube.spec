# -*- mode: python ; coding: utf-8 -*-

"""PyInstaller spec for AutoTube Creator (Windows one-folder build).

FFmpeg/FFprobe are NOT bundled by default to avoid redistribution/legal
ambiguity and to avoid downloading binaries silently. The application looks for
them in this order:

1. ``ffmpeg`` / ``ffprobe`` on ``PATH``.
2. A bundled directory next to the frozen executable:
   - ``<dist>/autotube/ffmpeg/ffmpeg.exe``
   - ``<dist>/autotube/ffmpeg/ffprobe.exe``

To produce a fully portable build, copy your licensed FFmpeg/FFprobe binaries
into ``dist/autotube/ffmpeg/`` after running PyInstaller. See
``docs/packaging.md``.
"""

from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []

datas, binaries, hiddenimports = collect_all("PySide6")

a = Analysis(
    ["entrypoint.py"],
    pathex=["../src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tests", "pytest", "_pytest", "licensing_server"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="autotube",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    version="version_info.txt",
    icon="app.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="autotube",
)
