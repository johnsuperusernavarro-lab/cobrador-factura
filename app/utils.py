"""
utils.py — Resolución de rutas para ejecución desde fuente y desde .exe compilado

Cuando PyInstaller congela el app:
  - sys.frozen = True
  - sys._MEIPASS = carpeta temporal con los recursos empaquetados
  - sys.executable = ruta del .exe

Cuando se ejecuta desde fuente:
  - Path(__file__).parent.parent = cobrador/
"""

import sys
from pathlib import Path


def get_bundle_dir() -> Path:
    """
    Directorio raíz de recursos empaquetados (styles/, resources/).
    - Compilado: sys._MEIPASS  (carpeta temporal del bundle)
    - Fuente:    cobrador/
    """
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).parent.parent


def get_data_dir() -> Path:
    """
    Directorio para datos persistentes del usuario (cobros.db).
    - Compilado: carpeta junto al .exe  (persiste entre ejecuciones)
    - Fuente:    cobrador/data/
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "data"
    return Path(__file__).parent.parent / "data"
