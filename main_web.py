#!/usr/bin/env python3
"""
main_web.py — Entry point web del Cobrador de Facturas (FastAPI)

Arranca el servidor en localhost:8000 y abre el navegador automaticamente.
Uso:
    python main_web.py
"""

import sys
import os
import threading
import webbrowser
import time
from pathlib import Path

# UTF-8 en terminal Windows
if sys.platform == "win32":
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except AttributeError:
        pass

# Cuando corre como .exe de PyInstaller, los recursos estan en sys._MEIPASS
if getattr(sys, "frozen", False):
    _BASE = Path(sys._MEIPASS)
else:
    _BASE = Path(__file__).parent

os.chdir(_BASE)

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from app.database import init_db
from app.api import router

# ── App FastAPI ──────────────────────────────────────────────────────────────
app = FastAPI(title="Cobrador de Facturas", docs_url=None, redoc_url=None)

# Archivos estaticos (CSS, JS, imagenes)
app.mount("/static", StaticFiles(directory="web/static"), name="static")

# Rutas de la API
app.include_router(router, prefix="/api")


# ── Paginas HTML ─────────────────────────────────────────────────────────────
PAGES = {"cartera", "pdfs", "plantillas", "contifico", "ajustes"}

@app.get("/")
def index():
    return FileResponse("web/index.html")

@app.get("/{page}")
def page(page: str):
    if page in PAGES:
        return FileResponse(f"web/{page}.html")
    return FileResponse("web/index.html")


# ── Arranque ─────────────────────────────────────────────────────────────────
def _abrir_navegador():
    time.sleep(1.2)
    webbrowser.open("http://localhost:8000")


def main():
    init_db()
    print("=" * 50)
    print("  Cobrador de Facturas — version web")
    print("  http://localhost:8000")
    print("  Presiona Ctrl+C para cerrar")
    print("=" * 50)
    threading.Thread(target=_abrir_navegador, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")


if __name__ == "__main__":
    main()
