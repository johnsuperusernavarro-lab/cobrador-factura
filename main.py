#!/usr/bin/env python3
"""
main.py — Entry point del Cobrador de Facturas (PyQt5)

Uso:
    python main.py
"""

import sys
import os
from pathlib import Path

# UTF-8 en terminal Windows
if sys.platform == "win32":
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except AttributeError:
        pass

# Asegurar que el directorio de trabajo sea el del script
os.chdir(Path(__file__).parent)

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QCoreApplication
from PyQt5.QtGui import QIcon

from app.database import init_db
from app.ui.main_window import MainWindow
from app.utils import get_bundle_dir

ICON_PATH = get_bundle_dir() / "resources" / "icon.ico"


def main():
    # DPI alto en Windows
    QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("Cobrador de Facturas")
    app.setOrganizationName("")

    if ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(ICON_PATH)))

    # Inicializar base de datos
    init_db()

    # Ventana principal
    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
