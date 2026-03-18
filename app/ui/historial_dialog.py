"""
app/ui/historial_dialog.py — Diálogo de historial de cargas

Permite ver las últimas N cargas de cartera y restaurar una carga anterior
sin necesidad de tener el archivo XLS original.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QSizePolicy,
)

from app import database as db

_PINE  = "#286983"
_TEXT  = "#575279"
_MUTED = "#9893a5"
_SURF  = "#fffaf3"
_OVR   = "#f2e9e1"


class HistorialDialog(QDialog):
    """
    Muestra el historial de cargas y permite restaurar una anterior.
    Si el usuario confirma la restauración, `self.facturas_restauradas`
    contiene las facturas; de lo contrario es None.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Historial de cargas")
        self.setMinimumSize(680, 400)
        self.facturas_restauradas: list[dict] | None = None

        self._build_ui()
        self._cargar_historial()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(16, 14, 16, 14)

        title = QLabel("Historial de cargas de cartera")
        title.setStyleSheet(f"font-size:15px; font-weight:700; color:{_TEXT};")
        root.addWidget(title)

        info = QLabel(
            "Se guardan automáticamente las últimas 5 cargas. "
            "Selecciona una fila y usa los botones para restaurar o eliminar."
        )
        info.setStyleSheet(f"font-size:12px; color:{_MUTED};")
        info.setWordWrap(True)
        root.addWidget(info)

        self._tabla = QTableWidget(0, 5)
        self._tabla.setHorizontalHeaderLabels(
            ["Fecha", "Software", "Facturas", "Monto Total", "Archivo"]
        )
        self._tabla.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self._tabla.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self._tabla.setSelectionBehavior(QTableWidget.SelectRows)
        self._tabla.setSelectionMode(QTableWidget.SingleSelection)
        self._tabla.verticalHeader().setVisible(False)
        self._tabla.setAlternatingRowColors(True)
        self._tabla.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._tabla.setStyleSheet(
            f"QTableWidget {{ background:{_SURF}; border:1px solid #d6cec5; border-radius:8px; }}"
            f"QHeaderView::section {{ background:#ede5dc; color:{_MUTED}; font-size:12px; "
            f"font-weight:600; padding:6px 10px; border:none; }}"
            f"QTableWidget::item {{ padding:6px 10px; color:{_TEXT}; font-size:12px; }}"
            f"QTableWidget::item:alternate {{ background:#f5efe7; }}"
            f"QTableWidget::item:selected {{ background:#dde8ed; color:{_PINE}; }}"
        )
        root.addWidget(self._tabla)

        btn_row = QHBoxLayout()

        self._btn_restaurar = QPushButton("🔄  Restaurar esta carga")
        self._btn_restaurar.setStyleSheet(
            f"QPushButton {{ background:{_PINE}; color:#fff; border:none; "
            f"border-radius:7px; padding:6px 16px; font-size:12px; font-weight:600; }}"
            f"QPushButton:hover {{ background:#1d4f63; }}"
            f"QPushButton:disabled {{ background:#cfc8be; }}"
        )
        self._btn_restaurar.setEnabled(False)
        self._btn_restaurar.clicked.connect(self._restaurar)

        self._btn_eliminar = QPushButton("🗑  Eliminar")
        self._btn_eliminar.setStyleSheet(
            f"QPushButton {{ background:#b4637a; color:#fff; border:none; "
            f"border-radius:7px; padding:6px 14px; font-size:12px; font-weight:600; }}"
            f"QPushButton:hover {{ background:#9e5269; }}"
            f"QPushButton:disabled {{ background:#cfc8be; }}"
        )
        self._btn_eliminar.setEnabled(False)
        self._btn_eliminar.clicked.connect(self._eliminar)

        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.setStyleSheet(
            f"QPushButton {{ background:{_OVR}; color:{_TEXT}; border:none; "
            f"border-radius:7px; padding:6px 14px; font-size:12px; }}"
            f"QPushButton:hover {{ background:#e0d7cf; }}"
        )
        btn_cerrar.clicked.connect(self.reject)

        btn_row.addWidget(self._btn_restaurar)
        btn_row.addWidget(self._btn_eliminar)
        btn_row.addStretch()
        btn_row.addWidget(btn_cerrar)
        root.addLayout(btn_row)

        self._tabla.selectionModel().selectionChanged.connect(self._on_seleccion)

    def _cargar_historial(self):
        self._historial = db.get_historial_cargas(limit=10)
        self._tabla.setRowCount(len(self._historial))
        for i, h in enumerate(self._historial):
            fecha = (h.get("fecha_carga") or "")[:16].replace("T", " ")
            self._tabla.setItem(i, 0, _item(fecha))
            self._tabla.setItem(i, 1, _item(h.get("software_origen") or "—"))
            self._tabla.setItem(i, 2, _item(str(h.get("n_facturas", 0))))
            monto = h.get("monto_total", 0) or 0
            self._tabla.setItem(i, 3, _item(f"${monto:,.2f}"))
            self._tabla.setItem(i, 4, _item(h.get("nombre_archivo") or "—"))

        if not self._historial:
            self._tabla.setRowCount(1)
            vacio = QTableWidgetItem("Sin cargas guardadas todavía")
            vacio.setForeground(Qt.GlobalColor.gray)
            self._tabla.setItem(0, 0, vacio)

    def _on_seleccion(self):
        tiene = bool(self._tabla.selectedItems())
        self._btn_restaurar.setEnabled(tiene and bool(self._historial))
        self._btn_eliminar.setEnabled(tiene and bool(self._historial))

    def _restaurar(self):
        row = self._tabla.currentRow()
        if row < 0 or row >= len(self._historial):
            return
        h = self._historial[row]
        fecha = (h.get("fecha_carga") or "")[:16].replace("T", " ")
        resp = QMessageBox.question(
            self, "Restaurar carga",
            f"¿Restaurar la cartera cargada el {fecha}?\n"
            f"({h.get('n_facturas', 0)} facturas — {h.get('software_origen', '')})\n\n"
            "La cartera activa actual será reemplazada."
        )
        if resp != QMessageBox.Yes:
            return

        self.facturas_restauradas = db.restaurar_desde_historial(h["id"])
        self.accept()

    def _eliminar(self):
        row = self._tabla.currentRow()
        if row < 0 or row >= len(self._historial):
            return
        h = self._historial[row]
        fecha = (h.get("fecha_carga") or "")[:16].replace("T", " ")
        resp = QMessageBox.question(
            self, "Eliminar entrada",
            f"¿Eliminar la carga del {fecha} del historial?\n"
            "Esta acción no se puede deshacer."
        )
        if resp != QMessageBox.Yes:
            return

        db.eliminar_carga_historial(h["id"])
        self._cargar_historial()
        self._btn_restaurar.setEnabled(False)
        self._btn_eliminar.setEnabled(False)


def _item(text: str) -> QTableWidgetItem:
    it = QTableWidgetItem(str(text))
    it.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
    return it
