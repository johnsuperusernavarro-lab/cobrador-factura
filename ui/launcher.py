"""
ui/launcher.py — Pantalla de inicio de CONDORNEXUS

Primera ventana que ve el usuario. Muestra la identidad de marca
y el botón para entrar al sistema.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QFont
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame,
)

from app.utils import get_bundle_dir

ICON_PATH = get_bundle_dir() / "resources" / "icon.ico"

# Paleta Rosé Pine Dawn
_BG      = "#faf4ed"
_SURFACE = "#fffaf3"
_OVERLAY = "#f2e9e1"
_TEXT    = "#575279"
_MUTED   = "#9893a5"
_PINE    = "#286983"   # teal principal
_PINE_DK = "#1d4f63"   # teal oscuro
_PINE_LT = "#3a7d9a"   # teal hover header
_GOLD    = "#ea9d34"   # acento dorado — color de "NEXUS"


class LauncherWindow(QDialog):
    """Pantalla de bienvenida de CONDORNEXUS."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CONDORNEXUS")
        self.setFixedSize(460, 360)
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)

        if ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(ICON_PATH)))

        self._build_ui()
        self._apply_styles()

    # ── UI ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())

        # Franja separadora dorada — conecta el color "NEXUS" del header con el cuerpo
        sep = QFrame()
        sep.setFixedHeight(3)
        sep.setStyleSheet(f"background: {_GOLD}; border: none;")
        root.addWidget(sep)

        root.addWidget(self._build_body())

    def _build_header(self) -> QFrame:
        """Cabecera oscura con logo y nombre de marca."""
        header = QFrame()
        header.setObjectName("launcher-header")
        header.setFixedHeight(208)

        lay = QVBoxLayout(header)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(0)
        lay.setContentsMargins(24, 20, 24, 16)

        # ── Logo mark: condor + teléfono ──────────────────────────────────
        logo_lbl = QLabel("🦅  📞")
        logo_lbl.setAlignment(Qt.AlignCenter)
        logo_lbl.setObjectName("launcher-logo")
        lay.addWidget(logo_lbl)

        lay.addSpacing(10)

        # ── Nombre de marca: CONDOR + NEXUS lado a lado ───────────────────
        brand_row = QHBoxLayout()
        brand_row.setSpacing(0)
        brand_row.setAlignment(Qt.AlignCenter)

        # "CONDOR" — blanco, peso normal, letras espaciadas (serenidad, confianza)
        condor_lbl = QLabel("CONDOR")
        condor_lbl.setObjectName("brand-condor")
        condor_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # "NEXUS" — dorado, peso pesado (energía, conexión, acción)
        nexus_lbl = QLabel("NEXUS")
        nexus_lbl.setObjectName("brand-nexus")
        nexus_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        brand_row.addStretch()
        brand_row.addWidget(condor_lbl)
        brand_row.addWidget(nexus_lbl)
        brand_row.addStretch()
        lay.addLayout(brand_row)

        lay.addSpacing(8)

        # ── Tagline ───────────────────────────────────────────────────────
        tagline = QLabel("Gestión inteligente de cuentas por cobrar")
        tagline.setAlignment(Qt.AlignCenter)
        tagline.setObjectName("launcher-tagline")
        lay.addWidget(tagline)

        lay.addSpacing(4)

        version = QLabel("v3.0  •  Modo local")
        version.setAlignment(Qt.AlignCenter)
        version.setObjectName("launcher-version")
        lay.addWidget(version)

        return header

    def _build_body(self) -> QFrame:
        """Cuerpo claro con badges de características y botón de inicio."""
        body = QFrame()
        body.setObjectName("launcher-body")

        lay = QVBoxLayout(body)
        lay.setAlignment(Qt.AlignCenter)
        lay.setContentsMargins(36, 22, 36, 22)
        lay.setSpacing(14)

        # ── Badges de características ─────────────────────────────────────
        badges_row = QHBoxLayout()
        badges_row.setSpacing(16)
        badges_row.setAlignment(Qt.AlignCenter)

        for texto in ("✓  Sin servidor", "✓  Sin internet", "✓  100% local"):
            badge = QLabel(texto)
            badge.setObjectName("launcher-badge")
            badges_row.addWidget(badge)

        lay.addLayout(badges_row)

        # ── Botón principal ───────────────────────────────────────────────
        self._btn_iniciar = QPushButton("▶   Entrar a CONDORNEXUS")
        self._btn_iniciar.setObjectName("btn-iniciar")
        self._btn_iniciar.setFixedHeight(46)
        self._btn_iniciar.setCursor(Qt.PointingHandCursor)
        self._btn_iniciar.clicked.connect(self.accept)
        lay.addWidget(self._btn_iniciar)

        return body

    # ── Estilos ──────────────────────────────────────────────────────────────

    def _apply_styles(self):
        self.setStyleSheet(f"""
            QDialog {{
                background: {_BG};
            }}

            /* ══ HEADER ══════════════════════════════════════════════════ */

            QFrame#launcher-header {{
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1a3d4f,
                    stop:1 {_PINE}
                );
            }}

            /* Logo — condor + teléfono */
            QLabel#launcher-logo {{
                font-size: 36px;
                background: transparent;
                border: none;
                padding: 0;
            }}

            /* "CONDOR" — blanco, peso normal, letras más separadas */
            QLabel#brand-condor {{
                font-family: "Segoe UI", Arial, sans-serif;
                font-size: 27px;
                font-weight: 400;
                color: rgba(255, 255, 255, 0.96);
                background: transparent;
                border: none;
                letter-spacing: 5px;
                padding-right: 2px;
            }}

            /* "NEXUS" — dorado, peso extrabold, compacto */
            QLabel#brand-nexus {{
                font-family: "Segoe UI", Arial, sans-serif;
                font-size: 27px;
                font-weight: 800;
                color: {_GOLD};
                background: transparent;
                border: none;
                letter-spacing: 1px;
            }}

            QLabel#launcher-tagline {{
                font-family: "Segoe UI", Arial, sans-serif;
                font-size: 12px;
                color: rgba(255, 255, 255, 0.70);
                background: transparent;
                border: none;
            }}

            QLabel#launcher-version {{
                font-family: "Segoe UI", Arial, sans-serif;
                font-size: 11px;
                color: rgba(255, 255, 255, 0.45);
                background: transparent;
                border: none;
            }}

            /* ══ BODY ════════════════════════════════════════════════════ */

            QFrame#launcher-body {{
                background: {_SURFACE};
            }}

            QLabel#launcher-badge {{
                font-family: "Segoe UI", Arial, sans-serif;
                font-size: 12px;
                color: {_PINE};
                background: transparent;
                border: none;
                font-weight: 500;
            }}

            /* ══ BOTÓN PRINCIPAL ═════════════════════════════════════════ */

            QPushButton#btn-iniciar {{
                background: {_PINE};
                color: #ffffff;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: 700;
                font-family: "Segoe UI", Arial, sans-serif;
                letter-spacing: 0.5px;
            }}

            QPushButton#btn-iniciar:hover {{
                background: {_PINE_DK};
            }}

            QPushButton#btn-iniciar:pressed {{
                background: #163d4d;
            }}
        """)
