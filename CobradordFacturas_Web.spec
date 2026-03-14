# -*- mode: python ; coding: utf-8 -*-
"""
CobradordFacturas_Web.spec
Empaqueta la version web (FastAPI + HTML/JS) como .exe para Windows.

Uso:
    python -m PyInstaller CobradordFacturas_Web.spec --clean
o simplemente:
    BUILD_WEB.bat
"""
from PyInstaller.utils.hooks import collect_all, collect_data_files

# ── Datos a incluir en el bundle ─────────────────────────────────────────────
datas = [
    ('web',               'web'),              # paginas HTML, CSS, JS
    ('resources/icon.ico','resources/'),       # icono de la app
]

# pdfplumber y pdfminer necesitan sus archivos de datos
tmp = collect_all('pdfplumber')
datas += tmp[0]
binaries  = tmp[1]
hiddenimports = tmp[2]

tmp = collect_all('pdfminer')
datas    += tmp[0]
binaries += tmp[1]
hiddenimports += tmp[2]

# ── Imports ocultos ───────────────────────────────────────────────────────────
hiddenimports += [
    # uvicorn
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.loops.asyncio',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.http.h11_impl',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    # fastapi / starlette
    'fastapi',
    'starlette',
    'starlette.middleware',
    'starlette.responses',
    'starlette.routing',
    'starlette.staticfiles',
    'starlette.requests',
    # pydantic
    'pydantic',
    'pydantic.v1',
    # anyio
    'anyio',
    'anyio._backends._asyncio',
    # h11
    'h11',
    # multipart (subida de archivos)
    'multipart',
    # servicios existentes
    'xlrd',
    'rapidfuzz',
    'rapidfuzz.fuzz',
    'rapidfuzz.process',
    # stdlib (a veces PyInstaller no los detecta)
    'smtplib',
    'ssl',
    'email.message',
    'sqlite3',
    'json',
    'threading',
    'webbrowser',
    'tempfile',
    'urllib.request',
    'urllib.error',
    'urllib.parse',
]

# ── Analisis ──────────────────────────────────────────────────────────────────
a = Analysis(
    ['main_web.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt5', 'tkinter', 'matplotlib', 'numpy', 'pandas'],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CobradordFacturas',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,          # muestra ventana de terminal (usuario ve que el servidor corre)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['resources\\icon.ico'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='CobradordFacturas',
)
