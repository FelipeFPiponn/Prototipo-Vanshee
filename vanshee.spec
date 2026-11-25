# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules
from pathlib import Path

block_cipher = None

# Recolectar paquetes complejos con DLLs y recursos
datas = [
    ('src/web', 'src/web'),
    ('config', 'config'),
]
binaries = []
hiddenimports = [
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'fastapi',
    'starlette',
    'starlette.middleware',
    'starlette.middleware.cors',
    'starlette.staticfiles',
    'pydantic',
    'pydantic_settings',
    'webview',
    'webview.platforms.winforms',
    'tkinter',
    'tkinter.ttk',
    'sounddevice',
    'edge_tts',
    'psutil',
    'win32gui',
    'win32con',
    'win32api',
    'win32process',
    'pyautogui',
    'pygetwindow',
    'pyperclip',
    'sqlite3',
    'numpy',
]

# Auto-recolección de paquetes de IA
for pkg in ['ctranslate2', 'faster_whisper', 'sounddevice', 'webview']:
    try:
        pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
        datas += pkg_datas
        binaries += pkg_binaries
        hiddenimports += pkg_hidden
    except Exception as e:
        print(f"[Warning Hook] No se pudo recolectar {pkg}: {e}")

try:
    hiddenimports += collect_submodules('src')
except Exception as e:
    print(f"[Warning Hook] No se pudieron recolectar submodulos de src: {e}")

a = Analysis(
    ['run_ui.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'IPython', 'notebook', 'pytest', 'tests'],
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
    name='Vanshee',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 100% Sin consola negra de terminal
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Vanshee',
)
