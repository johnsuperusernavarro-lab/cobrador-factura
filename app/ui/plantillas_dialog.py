"""
plantillas_dialog.py — Diálogo para editar plantillas de mensajes
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QLineEdit, QTabWidget,
    QWidget, QFrame, QMessageBox
)
from PyQt5.QtGui import QFont

from app import database as db


class PlantillasDialog(QDialog):
    """Permite editar las 4 plantillas (tipo×canal) guardadas en SQLite."""

    COMBOS = [
        ("por_vencer", "email",     "Por vencer — Email"),
        ("por_vencer", "whatsapp",  "Por vencer — WhatsApp"),
        ("vencida",    "email",     "Vencida — Email"),
        ("vencida",    "whatsapp",  "Vencida — WhatsApp"),
    ]

    VARS = "{cliente}  {factura_no}  {fecha}  {total}  {descripcion}"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._editores: dict[tuple, dict] = {}
        self._setup_ui()
        self._cargar()

    def _setup_ui(self):
        self.setWindowTitle("Editar Plantillas de Mensajes")
        self.setMinimumSize(680, 560)
        self.setModal(True)

        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(20, 20, 20, 16)

        # Encabezado
        titulo = QLabel("Plantillas de mensajes")
        font = QFont()
        font.setPointSize(14)
        font.setWeight(QFont.Bold)
        titulo.setFont(font)
        titulo.setStyleSheet("color: #575279;")
        root.addWidget(titulo)

        # Variables disponibles
        vars_lbl = QLabel(f"Variables disponibles: {self.VARS}")
        vars_lbl.setStyleSheet(
            "color: #9893a5; font-size: 11px; "
            "background: #f2e9e1; border-radius: 6px; padding: 4px 10px;"
        )
        vars_lbl.setWordWrap(True)
        root.addWidget(vars_lbl)

        # Tabs por plantilla
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        for tipo, canal, etiqueta in self.COMBOS:
            tab = QWidget()
            tab_layout = QVBoxLayout(tab)
            tab_layout.setSpacing(8)
            tab_layout.setContentsMargins(12, 14, 12, 8)

            edits = {}

            if canal == "email":
                asunto_lbl = QLabel("Asunto:")
                asunto_lbl.setStyleSheet("color: #9893a5; font-size: 11px; font-weight: 600;")
                tab_layout.addWidget(asunto_lbl)
                asunto_edit = QLineEdit()
                tab_layout.addWidget(asunto_edit)
                edits["asunto"] = asunto_edit

            cuerpo_lbl = QLabel("Cuerpo del mensaje:")
            cuerpo_lbl.setStyleSheet("color: #9893a5; font-size: 11px; font-weight: 600;")
            tab_layout.addWidget(cuerpo_lbl)

            cuerpo_edit = QTextEdit()
            cuerpo_edit.setAcceptRichText(False)
            tab_layout.addWidget(cuerpo_edit, 1)
            edits["cuerpo"] = cuerpo_edit

            self.tabs.addTab(tab, etiqueta)
            self._editores[(tipo, canal)] = edits

        # Botones
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #e0d9d0;")
        root.addWidget(sep)

        botones = QHBoxLayout()
        botones.setSpacing(10)

        btn_reset = QPushButton("Restaurar originales")
        btn_reset.setProperty("class", "secondary")
        btn_reset.setToolTip("Vuelve a las plantillas instaladas por defecto")
        btn_reset.clicked.connect(self._restaurar)

        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.setProperty("class", "secondary")
        btn_cancelar.clicked.connect(self.reject)

        btn_guardar = QPushButton("Guardar cambios")
        btn_guardar.setProperty("class", "primary")
        btn_guardar.clicked.connect(self._guardar)

        botones.addWidget(btn_reset)
        botones.addStretch()
        botones.addWidget(btn_cancelar)
        botones.addWidget(btn_guardar)
        root.addLayout(botones)

    def _cargar(self):
        """Lee plantillas desde SQLite y las muestra en los editores."""
        for tipo, canal, _ in self.COMBOS:
            plantilla = db.get_plantilla(tipo, canal)
            if not plantilla:
                continue
            edits = self._editores[(tipo, canal)]
            if "asunto" in edits:
                edits["asunto"].setText(plantilla.get("asunto") or "")
            edits["cuerpo"].setPlainText(plantilla.get("cuerpo") or "")

    def _guardar(self):
        """Persiste todos los editores en SQLite."""
        for tipo, canal, _ in self.COMBOS:
            edits = self._editores[(tipo, canal)]
            asunto = edits["asunto"].text() if "asunto" in edits else ""
            cuerpo = edits["cuerpo"].toPlainText()
            db.save_plantilla(tipo, canal, asunto, cuerpo)

        QMessageBox.information(
            self, "Guardado", "Plantillas guardadas correctamente."
        )
        self.accept()

    def _restaurar(self):
        """Restaura las plantillas por defecto en SQLite y en los editores."""
        resp = QMessageBox.question(
            self, "Restaurar",
            "¿Restaurar las plantillas originales? "
            "Se perderán los cambios guardados.",
            QMessageBox.Yes | QMessageBox.No
        )
        if resp != QMessageBox.Yes:
            return

        from app.database import PLANTILLAS_DEFAULT, save_plantilla
        for p in PLANTILLAS_DEFAULT:
            save_plantilla(p["tipo"], p["canal"], p["asunto"], p["cuerpo"])
        self._cargar()
        QMessageBox.information(self, "Restaurado", "Plantillas restauradas.")
