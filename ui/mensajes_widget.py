"""
ui/mensajes_widget.py — Centro de mensajes e historial de interacciones

Permite ver el historial de interacciones por cliente y registrar notas
manuales. Llama directamente a core/ sin HTTP.
"""

from PyQt5.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QTableWidget, QTableWidgetItem,
    QHeaderView, QLineEdit, QComboBox, QTextEdit,
    QSizePolicy, QMessageBox,
)

import core.database as db

_PINE  = "#286983"
_LOVE  = "#b4637a"
_GOLD  = "#ea9d34"
_TEXT  = "#575279"
_MUTED = "#9893a5"
_BG    = "#faf4ed"
_SURF  = "#fffaf3"
_OVR   = "#f2e9e1"


class MensajesWidget(QWidget):

    status_msg = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._anim: QPropertyAnimation | None = None  # referencia para evitar GC
        self._build_ui()
        self.refrescar()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        # ── Cabecera ──────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        title = QLabel("Centro de Mensajes")
        title.setStyleSheet(f"font-size:17px; font-weight:700; color:{_TEXT};")
        hdr.addWidget(title)
        hdr.addStretch()

        self._btn_nueva = QPushButton("+ Registrar interacción")
        self._btn_nueva.setStyleSheet(_btn(_PINE))
        self._btn_nueva.clicked.connect(self._toggle_panel)
        hdr.addWidget(self._btn_nueva)

        root.addLayout(hdr)

        # ── Panel de nueva nota (colapsable) ─────────────────────────────
        self._panel_nota = QFrame()
        self._panel_nota.setVisible(False)
        self._panel_nota.setMaximumHeight(0)
        self._panel_nota.setStyleSheet(
            f"QFrame {{ background:{_SURF}; border:1px solid {_PINE}; border-radius:10px; }}"
        )
        pn = QVBoxLayout(self._panel_nota)
        pn.setContentsMargins(16, 14, 16, 14)
        pn.setSpacing(10)

        pn.addWidget(_lbl("Registrar interacción manual"))

        row1 = QHBoxLayout()
        row1.setSpacing(10)

        self._n_cliente = QLineEdit()
        self._n_cliente.setPlaceholderText("Nombre del cliente")
        self._n_cliente.setStyleSheet(_input_style())

        self._n_factura = QLineEdit()
        self._n_factura.setPlaceholderText("Factura N°")
        self._n_factura.setStyleSheet(_input_style())

        self._n_tipo = QComboBox()
        self._n_tipo.addItems(["cobranza", "seguimiento", "otro"])
        self._n_tipo.setStyleSheet(_input_style())

        self._n_canal = QComboBox()
        self._n_canal.addItems(["manual", "email", "whatsapp", "llamada"])
        self._n_canal.setStyleSheet(_input_style())

        for w in (self._n_cliente, self._n_factura, self._n_tipo, self._n_canal):
            row1.addWidget(w)
        pn.addLayout(row1)

        self._n_contenido = QTextEdit()
        self._n_contenido.setPlaceholderText("Describe la interacción, resultado de llamada, acuerdo de pago, etc.")
        self._n_contenido.setFixedHeight(72)
        self._n_contenido.setStyleSheet(_input_style())
        pn.addWidget(self._n_contenido)

        btns = QHBoxLayout()
        btn_guardar = QPushButton("Guardar")
        btn_guardar.setStyleSheet(_btn(_PINE))
        btn_guardar.clicked.connect(self._guardar_nota)

        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.setStyleSheet(_btn(_OVR, color=_TEXT))
        btn_cancelar.clicked.connect(self._toggle_panel)

        btns.addWidget(btn_guardar)
        btns.addWidget(btn_cancelar)
        btns.addStretch()
        pn.addLayout(btns)

        root.addWidget(self._panel_nota)

        # ── Filtros ───────────────────────────────────────────────────────
        filtros = QHBoxLayout()
        filtros.setSpacing(10)

        self._f_cliente = QLineEdit()
        self._f_cliente.setPlaceholderText("Filtrar por cliente...")
        self._f_cliente.setMaximumWidth(220)
        self._f_cliente.setStyleSheet(_input_style())
        self._f_cliente.textChanged.connect(self._filtrar)

        self._f_tipo = QComboBox()
        self._f_tipo.addItems(["Todos los tipos", "cobranza", "seguimiento", "otro"])
        self._f_tipo.setStyleSheet(_input_style())
        self._f_tipo.currentTextChanged.connect(self._filtrar)

        # M13 — filtro por período de tiempo
        self._f_periodo = QComboBox()
        self._f_periodo.addItems(["Todos los períodos", "Últimos 7 días", "Últimos 30 días", "Este mes"])
        self._f_periodo.setStyleSheet(_input_style())
        self._f_periodo.currentTextChanged.connect(self._filtrar)

        self._lbl_total = QLabel("")
        self._lbl_total.setStyleSheet(f"font-size:12px; color:{_MUTED};")

        filtros.addWidget(self._f_cliente)
        filtros.addWidget(self._f_tipo)
        filtros.addWidget(self._f_periodo)
        filtros.addStretch()
        filtros.addWidget(self._lbl_total)
        root.addLayout(filtros)

        # ── Tabla de historial ───────────────────────────────────────────
        self._tabla = QTableWidget(0, 7)
        self._tabla.setHorizontalHeaderLabels(
            ["Fecha", "Cliente", "Factura", "Tipo", "Canal", "Enviado por", "Mensaje"]
        )
        self._tabla.horizontalHeader().setSectionResizeMode(6, QHeaderView.Stretch)
        self._tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self._tabla.setSelectionBehavior(QTableWidget.SelectRows)
        self._tabla.verticalHeader().setVisible(False)
        self._tabla.setAlternatingRowColors(True)
        self._tabla.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._tabla.setStyleSheet(
            f"QTableWidget {{ background:{_SURF}; border:1px solid #d6cec5; border-radius:10px; }}"
            f"QHeaderView::section {{ background:#ede5dc; color:{_MUTED}; font-size:12px; "
            f"font-weight:600; padding:6px 10px; border:none; }}"
            f"QTableWidget::item {{ padding:6px 10px; color:{_TEXT}; font-size:12px; }}"
            f"QTableWidget::item:alternate {{ background:#f5efe7; }}"
            f"QTableWidget::item:selected {{ background:#dde8ed; color:{_PINE}; }}"
        )
        root.addWidget(self._tabla)

        # Cache de todos los mensajes para filtrado local
        self._todos: list[dict] = []

    # ── Datos ────────────────────────────────────────────────────────────

    def refrescar(self):
        self._todos = db.get_mensajes_log(limit=300)
        self._filtrar()

    def _filtrar(self):
        from datetime import date, timedelta
        cliente = self._f_cliente.text().strip().lower()
        tipo    = self._f_tipo.currentText()
        periodo = self._f_periodo.currentText()

        # M13 — calcular fecha de corte según período seleccionado
        hoy = date.today()
        if periodo == "Últimos 7 días":
            corte = (hoy - timedelta(days=7)).isoformat()
        elif periodo == "Últimos 30 días":
            corte = (hoy - timedelta(days=30)).isoformat()
        elif periodo == "Este mes":
            corte = hoy.replace(day=1).isoformat()
        else:
            corte = None

        filtrados = [
            m for m in self._todos
            if (not cliente or cliente in (m.get("cliente") or "").lower())
            and (tipo == "Todos los tipos" or m.get("tipo") == tipo)
            and (corte is None or (m.get("fecha") or "") >= corte)
        ]

        self._tabla.setRowCount(len(filtrados))
        for i, m in enumerate(filtrados):
            fecha = (m.get("fecha") or "")[:16].replace("T", " ")
            self._tabla.setItem(i, 0, _item(fecha))
            self._tabla.setItem(i, 1, _item(m.get("cliente", "")))
            self._tabla.setItem(i, 2, _item(m.get("factura_no") or "—"))
            self._tabla.setItem(i, 3, _item(m.get("tipo") or "—"))
            self._tabla.setItem(i, 4, _item(m.get("canal") or "—"))
            self._tabla.setItem(i, 5, _item(m.get("enviado_por") or "manual"))
            preview = (m.get("contenido") or "")[:100]
            self._tabla.setItem(i, 6, _item(preview))

        self._lbl_total.setText(
            f"{len(filtrados)} registro(s)" if filtrados else ""
        )

    # ── Eventos ──────────────────────────────────────────────────────────

    def _toggle_panel(self):
        if self._panel_nota.isVisible():
            # Cerrar con animación
            self._anim = QPropertyAnimation(self._panel_nota, b"maximumHeight")
            self._anim.setDuration(180)
            self._anim.setStartValue(self._panel_nota.height())
            self._anim.setEndValue(0)
            self._anim.setEasingCurve(QEasingCurve.InCubic)
            def _on_close():
                self._panel_nota.setVisible(False)
                self._panel_nota.setMaximumHeight(0)
            self._anim.finished.connect(_on_close)
            self._anim.start()
        else:
            # Abrir con animación
            target_h = self._panel_nota.sizeHint().height() or 260
            self._panel_nota.setMaximumHeight(0)
            self._panel_nota.setVisible(True)
            self._anim = QPropertyAnimation(self._panel_nota, b"maximumHeight")
            self._anim.setDuration(220)
            self._anim.setStartValue(0)
            self._anim.setEndValue(target_h)
            self._anim.setEasingCurve(QEasingCurve.OutCubic)
            def _on_open():
                self._panel_nota.setMaximumHeight(16777215)
            self._anim.finished.connect(_on_open)
            self._anim.start()

    def buscar(self, texto: str) -> bool:
        """Aplica el texto al filtro de cliente y retorna True si hay resultados."""
        self._f_cliente.setText(texto)
        return self._tabla.rowCount() > 0

    def _guardar_nota(self):
        cliente  = self._n_cliente.text().strip()
        factura  = self._n_factura.text().strip()
        tipo     = self._n_tipo.currentText()
        canal    = self._n_canal.currentText()
        contenido = self._n_contenido.toPlainText().strip()

        if not cliente or not contenido:
            QMessageBox.warning(self, "Datos incompletos",
                                "El campo Cliente y Mensaje son obligatorios.")
            return

        db.registrar_mensaje_log(cliente, factura, tipo, canal, contenido, "manual")
        self.status_msg.emit("Nota registrada")

        self._n_cliente.clear()
        self._n_factura.clear()
        self._n_contenido.clear()
        if self._panel_nota.isVisible():
            self._toggle_panel()
        self.refrescar()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _lbl(text: str) -> QLabel:
    l = QLabel(text)
    l.setStyleSheet(f"font-size:12px; font-weight:600; color:{_MUTED};")
    return l


def _item(text: str) -> QTableWidgetItem:
    it = QTableWidgetItem(str(text))
    it.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
    return it


_BTN_HOVER = {
    _PINE: "#1d4f63",
    _OVR:  "#e0d7cf",
    _SURF: "#f2e9e1",
}


def _btn(bg: str, color: str = "#ffffff") -> str:
    hover = _BTN_HOVER.get(bg, "#ddd0c8")
    return (f"QPushButton {{ background:{bg}; color:{color}; border:none; "
            f"border-radius:7px; padding:5px 14px; font-size:12px; font-weight:600; }}"
            f"QPushButton:hover {{ background:{hover}; }}")


def _input_style() -> str:
    return (f"background:{_BG}; border:1px solid #d6cec5; border-radius:7px; "
            f"padding:5px 8px; color:{_TEXT}; font-size:12px;")
