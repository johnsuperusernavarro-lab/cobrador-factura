#!/usr/bin/env python3
"""
main.py — Punto de entrada del Cobrador de Facturas (Desktop v3.0)

Ejecutar:
    python main.py            ← doble clic en Windows / lanzador directo
    python -m main            ← equivalente via módulo

Arquitectura:
    main.py  →  ui/launcher.py  →  ui/main_window.py
                                     ├── ui/dashboard_widget.py   (core/)
                                     ├── ui/acciones_widget.py    (core/)
                                     ├── ui/mensajes_widget.py    (core/)
                                     ├── app/ui/cobros_widget.py  (app/services/)
                                     └── app/ui/pdf_drop_widget.py

No requiere servidor HTTP. Toda la lógica está en core/ y app/services/.
"""

# Delega completamente a main/__main__.py para evitar duplicación
from main.__main__ import run

if __name__ == "__main__":
    run()
