# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

datas = [
    ('stele/runtime/manifest.json', 'stele/runtime'),
    ('stele/ui/assets', 'stele/ui/assets'),
]

datas += collect_data_files('reportlab')

# PAR2 recovery data uses an external par2 program (par2cmdline-turbo,
# GPL-2.0). Drop par2.exe into tools/ before building to bundle it; ship its
# license and a source link in THIRD_PARTY_NOTICES.txt.
import os
binaries = []
if os.path.isfile('tools/par2.exe'):
    binaries.append(('tools/par2.exe', 'tools'))

hiddenimports = [
    'comtypes',
    'comtypes.client',
    'comtypes.stream',
    'keyring.backends.Windows',
    'reportlab.pdfgen.canvas',
    'reportlab.lib.units',
    'reportlab.platypus',
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'huggingface_hub',
    'httpx',
    'sqlite3',
]
hiddenimports += collect_submodules('keyring.backends')

a = Analysis(
    ['stele/app.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'torch', 'IPython', 'pytest'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Qt 6.11 on Windows uses the OS ICU API. An unrelated ICU from a
# tool's PATH (for example Poppler) exports versioned symbols and prevents
# QtWidgets from loading. Leave these OS dependencies to Windows.
a.binaries = [entry for entry in a.binaries
              if entry[0].lower() != 'icuuc.dll'
              and not (entry[0].lower().startswith('icudt')
                       and entry[0].lower().endswith('.dll'))]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Stele',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
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
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Stele',
)
