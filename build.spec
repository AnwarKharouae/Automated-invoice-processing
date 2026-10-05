# PyInstaller spec for InvoiceReviewer
# Build: pyinstaller build.spec --noconfirm --clean

import os
APP_DIR = os.path.abspath('.')

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[APP_DIR],
    binaries=[],
    datas=[
        # ship ui/ and core/ as raw folders so Python can import them at runtime
        ('ui', 'ui'),
        ('core', 'core'),
        # also ship resources
        ('resources', 'resources'),
    ],
    hiddenimports=[
        'ui', 'ui.main_window', 'ui.review_table', 'ui.image_viewer',
        'ui.export_dialog', 'ui.preferences_dialog', 'ui.schema_dialog',
        'core', 'core.worker', 'core.pipeline', 'core.excel_export',
        'core.sound', 'core.session', 'core.preferences',
        'core.ollama_manager', 'core.paths',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        'paddleocr', 'paddle', 'paddlex', 'paddlepaddle',
        'streamlit', 'plotly',
        'matplotlib', 'notebook', 'jupyter', 'ipykernel',
        'pytesseract',
        'tkinter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='InvoiceReviewer',
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
    icon='icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='InvoiceReviewer',
)