# -*- mode: python ; coding: utf-8 -*-
# Standalone EMBERDEEP build:  pyinstaller emberdeep.spec   -> dist/emberdeep
block_cipher = None
a = Analysis(
    ["game.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    excludes=["tkinter", "numpy", "PIL"],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name="emberdeep",
    debug=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)
