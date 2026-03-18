"""
ui/acciones_widget.py — Pestaña de acciones sugeridas y scores

Muestra la tabla de scores de clientes y la lista de acciones pendientes.
Llama directamente a core/ sin HTTP.
"""

import threading
from datetime import date, timedelta

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QTableWidget, QTableWidgetItem,
    QHeaderView, QSplitter, QMessageBox,
)

import core.database as db
from core.scoring import recalcular_todos_los_scores
from core.automation import evaluar_facturas
from ui.procesar_accion_dialog import ProcesarAccionDialog

_PINE   = "#286983"
_LOVE   = "#b4637a"
_GOLD   = "#ea9d34"
_TEXT   = "#575279"
_MUTED  = "#9893a5"   # sugerencias / placeholders
_SUBTLE = "#797593"   # encabezados de sección
_BG     = "#faf4ed"
_SURF   = "#fffaf3"
_OVR    = "#f2e9e1"


class AccionesWidget(QWidget):

    status_msg = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.refrescar()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        # ── Barra superior ───────────────────────────────────────────────
        top = QHBoxLayout()
        title = QLabel("Acciones Sugeridas")
        title.setStyleSheet(f"font-size:17px; font-weight:700; color:{_TEXT};")
        top.addWidget(title)
        top.addStretch()

        self._btn_evaluar = QPushButton("⚡  Evaluar ahora")
        self._btn_evaluar.setStyleSheet(_btn_style(_GOLD))
        self._btn_evaluar.setToolTip(
            "Genera la lista de acciones del día según las facturas en cartera.\n"
            "Ejecuta el motor de reglas y crea recordatorios de cobro."
        )
        self._btn_evaluar.clicked.connect(self._evaluar_ahora)
        top.addWidget(self._btn_evaluar)

        self._btn_scores = QPushButton("🔄  Recalcular scores")
        self._btn_scores.setStyleSheet(_btn_style(_PINE))
        self._btn_scores.setToolTip(
            "Actualiza el nivel de riesgo de cada cliente (Score 0–100).\n"
            "Usa el historial de pagos y días de atraso promedio."
        )
        self._btn_scores.clicked.connect(self._recalcular_scores)
        top.addWidget(self._btn_scores)

        btn_procesar = QPushButton("▶  Procesar por importancia")
        btn_procesar.setStyleSheet(_btn_style("#b4637a"))
        btn_procesar.setToolTip("Procesa las acciones ordenadas de mayor a menor urgencia")
        btn_procesar.clicked.connect(self._procesar_por_importancia)
        top.addWidget(btn_procesar)

        root.addLayout(top)

        # ── Splitter: scores arriba / acciones abajo ─────────────────────
        splitter = QSplitter(Qt.Vertical)

        # Scores
        scores_frame = QFrame()
        scores_frame.setStyleSheet(f"QFrame {{ background:{_SURF}; border:1px solid #d6cec5; border-radius:10px; }}")
        sf_lay = QVBoxLayout(scores_frame)
        sf_lay.setContentsMargins(12, 10, 12, 10)
        sf_lay.setSpacing(6)
        sf_lay.addWidget(_section_lbl("Score de clientes"))

        self._tabla_scores = QTableWidget(0, 6)
        self._tabla_scores.setHorizontalHeaderLabels(
            ["Cliente", "Score", "Clasificación", "Días prom. atraso", "Facturas vencidas", "Tono"]
        )
        hdr_s = self._tabla_scores.horizontalHeader()
        hdr_s.setSectionResizeMode(0, QHeaderView.Stretch)
        # M8 — tooltips explicativos en columnas de scores
        hdr_s.setToolTip(
            "Score 0–100: 0 = muy confiable, 100 = alto riesgo.\n"
            "Basado en días de atraso y cantidad de facturas vencidas.\n"
            "Tono: amable (0–35) · neutro (36–65) · firme (66–100)"
        )
        self._tabla_scores.setEditTriggers(QTableWidget.NoEditTriggers)
        self._tabla_scores.setSelectionBehavior(QTableWidget.SelectRows)
        self._tabla_scores.verticalHeader().setVisible(False)
        self._tabla_scores.setAlternatingRowColors(True)
        self._tabla_scores.setStyleSheet(_table_style())
        # M9 — selección en scores filtra acciones del mismo cliente
        self._tabla_scores.itemSelectionChanged.connect(self._on_score_seleccionado)
        sf_lay.addWidget(self._tabla_scores)
        splitter.addWidget(scores_frame)

        # Acciones
        acc_frame = QFrame()
        acc_frame.setStyleSheet(f"QFrame {{ background:{_SURF}; border:1px solid #d6cec5; border-radius:10px; }}")
        af_lay = QVBoxLayout(acc_frame)
        af_lay.setContentsMargins(12, 10, 12, 10)
        af_lay.setSpacing(6)
        af_lay.addWidget(_section_lbl("Acciones pendientes"))

        self._tabla_acciones = QTableWidget(0, 6)
        self._tabla_acciones.setHorizontalHeaderLabels(
            ["Cliente", "Factura", "Tipo", "Clasificación", "Mensaje", "Acciones"]
        )
        hdr_a = self._tabla_acciones.horizontalHeader()
        hdr_a.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Cliente
        hdr_a.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Factura
        hdr_a.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Tipo
        hdr_a.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Clasificación
        hdr_a.setSectionResizeMode(4, QHeaderView.Stretch)           # Mensaje — toma el resto
        hdr_a.setSectionResizeMode(5, QHeaderView.Fixed)             # Acciones — ancho fijo
        self._tabla_acciones.setColumnWidth(5, 140)
        self._tabla_acciones.verticalHeader().setDefaultSectionSize(36)
        self._tabla_acciones.setEditTriggers(QTableWidget.NoEditTriggers)
        self._tabla_acciones.setSelectionBehavior(QTableWidget.SelectRows)
        self._tabla_acciones.verticalHeader().setVisible(False)
        self._tabla_acciones.setAlternatingRowColors(True)
        self._tabla_acciones.setStyleSheet(_table_style())
        af_lay.addWidget(self._tabla_acciones)
        splitter.addWidget(acc_frame)

        splitter.setStretchFactor(0, 30)
        splitter.setStretchFactor(1, 70)
        root.addWidget(splitter)

    # ── Datos ────────────────────────────────────────────────────────────

    def refrescar(self):
        self._cargar_scores()
        self._cargar_acciones()

    def _cargar_scores(self):
        scores = db.get_todos_scores()
        self._tabla_scores.setRowCount(len(scores))
        _CLS_COLORS = {"confiable": _PINE, "medio": _GOLD, "riesgoso": _LOVE}

        for i, s in enumerate(scores):
            cls   = s.get("clasificacion", "medio")
            tono_map = {"confiable": "amable", "medio": "neutro", "riesgoso": "firme"}

            self._tabla_scores.setItem(i, 0, _item(s.get("cliente", "")))
            self._tabla_scores.setItem(i, 1, _item(f"{s.get('score', 50):.1f}"))
            it_cls = _item(cls)
            it_cls.setForeground(Qt.GlobalColor.white if False else
                                  QTableWidgetItem().foreground())
            # Color de texto de clasificación
            from PyQt5.QtGui import QColor
            it_cls.setForeground(QColor(_CLS_COLORS.get(cls, _TEXT)))
            self._tabla_scores.setItem(i, 2, it_cls)
            self._tabla_scores.setItem(i, 3, _item(f"{s.get('dias_promedio_atraso', 0):.1f} días"))
            self._tabla_scores.setItem(i, 4, _item(
                f"{s.get('facturas_vencidas', 0)} / {s.get('total_facturas', 0)}"
            ))
            self._tabla_scores.setItem(i, 5, _item(tono_map.get(cls, "neutro")))

    def _cargar_acciones(self):
        hoy = date.today().isoformat()
        acciones = db.get_acciones_pendientes(hoy)
        scores = {s["cliente"]: s for s in db.get_todos_scores()}

        self._tabla_acciones.setRowCount(len(acciones))
        _TIPO_LABELS = {
            "contactar_email":     "📧 Email",
            "contactar_whatsapp":  "💬 WhatsApp",
            "revisar":             "🔍 Revisar",
        }

        for i, a in enumerate(acciones):
            cls = scores.get(a["cliente"], {}).get("clasificacion", "medio")
            self._tabla_acciones.setItem(i, 0, _item(a.get("cliente", "")))
            self._tabla_acciones.setItem(i, 1, _item(a.get("factura_no", "—")))
            self._tabla_acciones.setItem(i, 2, _item(_TIPO_LABELS.get(a.get("tipo", ""), a.get("tipo", ""))))
            self._tabla_acciones.setItem(i, 3, _item(cls))
            msg = (a.get("mensaje_sugerido") or "")[:60]
            self._tabla_acciones.setItem(i, 4, _item(msg))

            # Botones de acción en columna 5
            btn_frame = QFrame()
            btn_lay = QHBoxLayout(btn_frame)
            btn_lay.setContentsMargins(4, 2, 4, 2)
            btn_lay.setSpacing(4)

            aid = a["id"]
            btn_mod = QPushButton("✎")
            btn_mod.setToolTip("Modificar tono y enviar")
            btn_mod.setStyleSheet(f"QPushButton {{ background:{_GOLD}; color:#fff; border:none; border-radius:4px; padding:4px 10px; min-height:28px; font-size:12px; }} QPushButton:hover {{ background:#c87e1c; }}")
            btn_mod.clicked.connect(lambda _, idx=i: self._modificar(idx))

            btn_ok = QPushButton("✓")
            btn_ok.setToolTip("Marcar como completada")
            btn_ok.setStyleSheet(f"QPushButton {{ background:{_PINE}; color:#fff; border:none; border-radius:4px; padding:4px 10px; min-height:28px; font-size:12px; }} QPushButton:hover {{ background:#1d4f63; }}")
            btn_ok.clicked.connect(lambda _, x=aid: self._completar(x))

            btn_pos = QPushButton("+1d")
            btn_pos.setToolTip("Posponer 1 día")
            btn_pos.setStyleSheet(f"QPushButton {{ background:{_OVR}; color:{_TEXT}; border:none; border-radius:4px; padding:4px 10px; min-height:28px; font-size:12px; }} QPushButton:hover {{ background:#e0d7cf; }}")
            btn_pos.clicked.connect(lambda _, x=aid: self._posponer(x))

            btn_lay.addWidget(btn_mod)
            btn_lay.addWidget(btn_ok)
            btn_lay.addWidget(btn_pos)
            self._tabla_acciones.setCellWidget(i, 5, btn_frame)

        if not acciones:
            self._tabla_acciones.setRowCount(1)
            empty = _item("✅  Sin acciones pendientes para hoy")
            empty.setForeground(__import__("PyQt5.QtGui", fromlist=["QColor"]).QColor(_MUTED))
            self._tabla_acciones.setItem(0, 0, empty)
            self._tabla_acciones.setSpan(0, 0, 1, 6)

    # ── Eventos ──────────────────────────────────────────────────────────

    def _evaluar_ahora(self):
        self._btn_evaluar.setEnabled(False)
        self._btn_evaluar.setText("Evaluando…")
        self.status_msg.emit("Evaluando facturas...")

        def _run():
            res = evaluar_facturas()
            msg = f"Evaluación lista: {res['acciones_creadas']} acciones generadas"
            def _done():
                self._btn_evaluar.setEnabled(True)
                self._btn_evaluar.setText("⚡  Evaluar ahora")
                self.status_msg.emit(msg)
                self.refrescar()
            QTimer.singleShot(0, _done)
        threading.Thread(target=_run, daemon=True).start()

    def _recalcular_scores(self):
        self._btn_scores.setEnabled(False)
        self._btn_scores.setText("Calculando…")
        self.status_msg.emit("Recalculando scores...")

        def _run():
            n = recalcular_todos_los_scores()
            def _done():
                self._btn_scores.setEnabled(True)
                self._btn_scores.setText("🔄  Recalcular scores")
                self.status_msg.emit(f"Scores actualizados: {n} clientes")
                self.refrescar()
            QTimer.singleShot(0, _done)
        threading.Thread(target=_run, daemon=True).start()

    def _on_score_seleccionado(self):
        """M9 — filtrar tabla de acciones al cliente seleccionado en scores."""
        rows = self._tabla_scores.selectedItems()
        if not rows:
            self._cargar_acciones()   # sin selección → mostrar todas
            return
        cliente = self._tabla_scores.item(rows[0].row(), 0)
        if not cliente:
            return
        nombre = cliente.text().lower()

        hoy = date.today().isoformat()
        acciones = db.get_acciones_pendientes(hoy)
        scores = {s["cliente"]: s for s in db.get_todos_scores()}

        filtradas = [a for a in acciones if nombre in a.get("cliente", "").lower()]
        self._tabla_acciones.setRowCount(0)

        _TIPO_LABELS = {
            "contactar_email":     "📧 Email",
            "contactar_whatsapp":  "💬 WhatsApp",
            "revisar":             "🔍 Revisar",
        }
        for i, a in enumerate(filtradas):
            cls = scores.get(a["cliente"], {}).get("clasificacion", "medio")
            self._tabla_acciones.insertRow(i)
            self._tabla_acciones.setItem(i, 0, _item(a.get("cliente", "")))
            self._tabla_acciones.setItem(i, 1, _item(a.get("factura_no", "—")))
            self._tabla_acciones.setItem(i, 2, _item(_TIPO_LABELS.get(a.get("tipo", ""), a.get("tipo", ""))))
            self._tabla_acciones.setItem(i, 3, _item(cls))
            self._tabla_acciones.setItem(i, 4, _item((a.get("mensaje_sugerido") or "")[:60]))

    def _completar(self, accion_id: int):
        db.completar_accion(accion_id)
        self.status_msg.emit("Acción completada")
        self._cargar_acciones()

    def _posponer(self, accion_id: int):
        nueva = (date.today() + timedelta(days=1)).isoformat()
        db.posponer_accion(accion_id, nueva)
        self.status_msg.emit("Acción pospuesta 1 día")
        self._cargar_acciones()

    def _procesar_por_importancia(self):
        hoy     = date.today().isoformat()
        acciones = db.get_acciones_pendientes(hoy)
        if not acciones:
            QMessageBox.information(self, "Sin acciones",
                                    "No hay acciones pendientes para hoy.")
            return
        scores      = {s["cliente"]: s for s in db.get_todos_scores()}
        facturas_idx = {f["factura_no"]: f for f in db.get_facturas_cache()}
        dlg = ProcesarAccionDialog(acciones, scores, facturas_idx, parent=self)
        dlg.exec_()
        self.refrescar()

    def _modificar(self, row_idx: int):
        """Abre el diálogo empezando por la acción de la fila seleccionada."""
        hoy     = date.today().isoformat()
        acciones = db.get_acciones_pendientes(hoy)
        if not acciones or row_idx >= len(acciones):
            return
        scores      = {s["cliente"]: s for s in db.get_todos_scores()}
        facturas_idx = {f["factura_no"]: f for f in db.get_facturas_cache()}
        dlg = ProcesarAccionDialog(acciones, scores, facturas_idx,
                                   start_index=row_idx, parent=self)
        dlg.exec_()
        self.refrescar()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _section_lbl(text: str) -> QLabel:
    l = QLabel(text)
    l.setStyleSheet(f"font-size:12px; font-weight:600; color:{_SUBTLE};")
    return l


def _item(text: str) -> QTableWidgetItem:
    it = QTableWidgetItem(str(text))
    it.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
    return it


# Mapa de colores hover por color base (opacity no funciona en Qt QSS)
_HOVER_COLORS = {
    _GOLD:    "#c87e1c",
    _PINE:    "#1d4f63",
    "#b4637a": "#9e5269",
}


def _btn_style(color: str) -> str:
    hover = _HOVER_COLORS.get(color, "#888")
    return (f"QPushButton {{ background:{color}; color:#fff; border:none; "
            f"border-radius:7px; padding:5px 14px; font-size:12px; font-weight:600; }}"
            f"QPushButton:hover {{ background:{hover}; }}"
            f"QPushButton:disabled {{ background:{_OVR}; color:{_MUTED}; }}")


def _table_style() -> str:
    return (f"QTableWidget {{ background:{_SURF}; border:none; border-radius:8px; gridline-color:#e8e0d8; }}"
            f"QHeaderView::section {{ background:#ede5dc; color:{_MUTED}; font-size:12px; "
            f"font-weight:600; padding:4px 8px; border:none; }}"
            f"QTableWidget::item {{ padding:4px 8px; color:{_TEXT}; font-size:12px; }}"
            f"QTableWidget::item:alternate {{ background:#f5efe7; }}"
            f"QTableWidget::item:selected {{ background:#dde8ed; color:{_PINE}; }}")
