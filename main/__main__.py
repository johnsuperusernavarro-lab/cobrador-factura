"""
main/__main__.py — Punto de entrada del Cobrador de Facturas (Desktop)

Uso:
    python -m main
    (o directamente mediante main.py en la raíz del proyecto)

Flujo:
    1. Muestra LauncherWindow (ventana pequeña con "Iniciar")
    2. Al hacer clic, abre MainWindow (aplicación completa)
    3. Restaura el Modo Inteligente si estaba activo en la sesión anterior
"""

import sys
import os
from pathlib import Path

# UTF-8 en Windows
if sys.platform == "win32":
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except AttributeError:
        pass

# Directorio de trabajo = raíz del proyecto
os.chdir(Path(__file__).parent.parent)

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QCoreApplication
from PyQt5.QtGui import QIcon

from app.database import init_db
from app.utils import get_bundle_dir
from core.automation import activar
from ui.launcher import LauncherWindow
from ui.main_window import MainWindow

ICON_PATH = get_bundle_dir() / "resources" / "icon.ico"


def run():
    # DPI alto en Windows
    QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("Cobrador de Facturas")
    app.setOrganizationName("")

    if ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(ICON_PATH)))

    # Inicializar base de datos SQLite
    init_db()

    # Activar el scheduler de automatización (siempre encendido)
    activar()

    # ── Paso 1: Launcher ────────────────────────────────────────────────
    launcher = LauncherWindow()
    if launcher.exec_() != LauncherWindow.Accepted:
        # El usuario cerró el launcher sin hacer clic en "Iniciar"
        sys.exit(0)

    # ── Paso 2: Ventana principal ────────────────────────────────────────
    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    run()
