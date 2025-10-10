# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['ScreamJam.py'],
    pathex=[],
    binaries=[],
    datas=[('Buildings', 'Buildings'), ('Characters', 'Characters'), ('Fonts', 'Fonts'), ('Maps', 'Maps'), ('Music', 'Music'), ('Tiles', 'Tiles'), ('UI', 'UI')],
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
    a.binaries,
    a.datas,
    [],
    name='ScreamJam',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['C:\\Users\\Jacob\\Documents\\PowerPlant\\icon.ico'],
)
