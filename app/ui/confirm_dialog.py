"""
confirm_dialog.py — Diálogo de confirmación antes del envío masivo
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QProgressBar
)
from PyQt5.QtGui import QFont


class ConfirmDialog(QDialog):
    """
    Muestra resumen antes del envío masivo:
    - N emails a enviar
    - N sin contacto (omitidos)
    - N ya enviados hoy (omitidos)

    Retorna QDialog.Accepted si el usuario confirma.
    """

    def __init__(self, n_emails: int, n_sin_contacto: int,
                 n_ya_enviados: int, parent=None):
        super().__init__(parent)
        self.n_emails      = n_emails
        self.n_sin_contacto = n_sin_contacto
        self.n_ya_enviados = n_ya_enviados
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("Confirmar envío masivo")
        self.setMinimumWidth(400)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(28, 28, 28, 24)

        # Título
        titulo = QLabel("Resumen de envío")
        font = QFont()
        font.setPointSize(14)
        font.setWeight(QFont.Bold)
        titulo.setFont(font)
        titulo.setStyleSheet("color: #575279;")
        layout.addWidget(titulo)

        # Separador
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #d6cec5;")
        layout.addWidget(sep)

        # Items del resumen
        items = [
            ("📧", f"{self.n_emails} email(s) a enviar", "#286983"),
            ("⚠️", f"{self.n_sin_contacto} sin contacto (serán omitidos)", "#ea9d34"),
            ("✓",  f"{self.n_ya_enviados} ya enviados hoy (serán omitidos)", "#9893a5"),
        ]

        for icon, texto, color in items:
            row = QHBoxLayout()
            icon_lbl = QLabel(icon)
            icon_lbl.setFixedWidth(28)
            icon_lbl.setAlignment(Qt.AlignCenter)

            txt_lbl = QLabel(texto)
            txt_lbl.setStyleSheet(f"color: {color}; font-size: 13px;")
            txt_lbl.setWordWrap(True)

            row.addWidget(icon_lbl)
            row.addWidget(txt_lbl, 1)
            layout.addLayout(row)

        # Barra de progreso (oculta hasta que comience el envío)
        self.progress = QProgressBar()
        self.progress.setRange(0, max(self.n_emails, 1))
        self.progress.setValue(0)
        self.progress.setVisible(False)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(10)
        layout.addWidget(self.progress)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #9893a5; font-size: 11px;")
        self.lbl_status.setVisible(False)
        layout.addWidget(self.lbl_status)

        # Separador
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet("color: #d6cec5;")
        layout.addWidget(sep2)

        # Aviso si no hay nada que enviar
        if self.n_emails == 0:
            aviso = QLabel("No hay emails pendientes de envío.")
            aviso.setStyleSheet("color: #9893a5; font-style: italic;")
            layout.addWidget(aviso)

        # Botones
        botones = QHBoxLayout()
        botones.setSpacing(10)

        self.btn_cancelar = QPushButton("Cancelar")
        self.btn_cancelar.setProperty("class", "secondary")
        self.btn_cancelar.clicked.connect(self.reject)

        self.btn_confirmar = QPushButton(
            "Enviar ahora" if self.n_emails > 0 else "Cerrar"
        )
        self.btn_confirmar.setProperty("class", "primary")
        self.btn_confirmar.clicked.connect(self.accept)
        if self.n_emails == 0:
            self.btn_cancelar.setVisible(False)

        botones.addStretch()
        botones.addWidget(self.btn_cancelar)
        botones.addWidget(self.btn_confirmar)
        layout.addLayout(botones)

    def mostrar_progreso(self, actual: int, total: int, cliente: str = ""):
        """Activa y actualiza la barra de progreso durante el envío."""
        self.progress.setVisible(True)
        self.lbl_status.setVisible(True)
        self.progress.setRange(0, total)
        self.progress.setValue(actual)
        self.lbl_status.setText(f"Enviando {actual}/{total}… {cliente}")
        self.btn_confirmar.setEnabled(False)
        self.btn_cancelar.setEnabled(False)
