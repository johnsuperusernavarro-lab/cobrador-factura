"""
main_window.py — QMainWindow principal del Cobrador de Facturas
"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout,
    QLabel, QStatusBar, QTabWidget, QPushButton
)

from app.ui.cobros_widget import CobrosWidget
from app.ui.pdf_drop_widget import PdfDropWidget
from app.ui.settings_dialog import SettingsDialog
from app.utils import get_bundle_dir

ICON_PATH = get_bundle_dir() / "resources" / "icon.ico"
QSS_PATH  = get_bundle_dir() / "styles"    / "styles.qss"


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cobrador de Facturas")
        self.setMinimumSize(960, 620)
        self.resize(1100, 700)

        if ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(ICON_PATH)))

        # ── Tabs ──────────────────────────────────────────────────────────
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.setTabPosition(QTabWidget.North)

        # Tab 1: Cartera XLS
        self._cobros = CobrosWidget()
        self._cobros.status_msg.connect(self._set_status)
        self._tabs.addTab(self._cobros, "📊  Cartera XLS")

        # Tab 2: PDF Rápido (drag & drop)
        self._pdf_drop = PdfDropWidget()
        self._pdf_drop.status_msg.connect(self._set_status)
        self._tabs.addTab(self._pdf_drop, "📄  PDF Rápido")

        self.setCentralWidget(self._tabs)

        # ── Status bar ────────────────────────────────────────────────────
        self._status = QStatusBar()
        self._status.setSizeGripEnabled(True)
        self.setStatusBar(self._status)
        self._set_status("Listo")

        lbl_empresa = QLabel("")
        lbl_empresa.setStyleSheet("color: #9893a5; font-size: 11px; padding-right: 8px;")
        self._status.addPermanentWidget(lbl_empresa)

        btn_ajustes = QPushButton("⚙  Ajustes")
        btn_ajustes.setFlat(True)
        btn_ajustes.setStyleSheet(
            "QPushButton { color: #9893a5; font-size: 11px; padding: 0 10px; "
            "border: none; background: transparent; }"
            "QPushButton:hover { color: #286983; }"
        )
        btn_ajustes.setToolTip("Configurar correo y WhatsApp")
        btn_ajustes.clicked.connect(self._abrir_ajustes)
        self._status.addPermanentWidget(btn_ajustes)

        # ── Estilos ───────────────────────────────────────────────────────
        self._cargar_estilos()

    def _cargar_estilos(self):
        if QSS_PATH.exists():
            self.setStyleSheet(QSS_PATH.read_text(encoding="utf-8"))

    def _set_status(self, msg: str):
        self._status.showMessage(msg, 8000)

    def _abrir_ajustes(self):
        dlg = SettingsDialog(self)
        dlg.exec_()
