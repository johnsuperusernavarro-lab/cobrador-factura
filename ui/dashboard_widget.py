"""
ui/dashboard_widget.py — Panel de control inteligente

Muestra métricas de la cartera, toggle del Modo Inteligente,
acciones sugeridas del día y actividad reciente.
Llama directamente a core/ sin HTTP.
"""

from datetime import date

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QFrame, QScrollArea,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QSizePolicy,
)

import core.database as db

# Paleta
_PINE   = "#286983"
_LOVE   = "#b4637a"
_GOLD   = "#ea9d34"
_IRIS   = "#907aa9"
_FOAM   = "#56949f"
_TEXT   = "#575279"
_MUTED  = "#9893a5"   # sugerencias / placeholders / valores secundarios
_SUBTLE = "#797593"   # encabezados de sección / etiquetas funcionales
_BG     = "#faf4ed"
_SURF   = "#fffaf3"
_OVR    = "#f2e9e1"


def _card(label: str, value_id: str, color: str, on_click=None) -> tuple[QFrame, QLabel]:
    card = QFrame()
    card.setStyleSheet(
        f"QFrame {{"
        f"  background:{_SURF};"
        f"  border-top: 1px solid #d6cec5;"
        f"  border-right: 1px solid #d6cec5;"
        f"  border-bottom: 1px solid #d6cec5;"
        f"  border-left: 4px solid {color};"
        f"  border-radius: 10px;"
        f"}}"
    )
    lay = QVBoxLayout(card)
    lay.setContentsMargins(12, 10, 12, 10)
    lay.setSpacing(3)

    lbl = QLabel(label)  # sin uppercase — más legible en pantallas pequeñas
    lbl.setStyleSheet(
        f"font-size:11px; font-weight:600; color:{_MUTED}; "
        f"background:transparent; border:none;"
    )
    lbl.setWordWrap(True)

    val = QLabel("—")
    val.setObjectName(value_id)
    val.setStyleSheet(
        f"font-size:22px; font-weight:700; color:{color}; "
        f"background:transparent; border:none;"
    )

    lay.addWidget(lbl)
    lay.addWidget(val)

    if on_click:
        card.setCursor(Qt.PointingHandCursor)
        card.setToolTip("Clic para ir a la sección")
        card.mousePressEvent = lambda e, cb=on_click: cb()

    return card, val


class DashboardWidget(QWidget):

    status_msg  = pyqtSignal(str)
    tab_request = pyqtSignal(int)   # índice del tab al que navegar (M5)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

        # Refresco automático cada 60 s
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refrescar)
        self._timer.start(60_000)

        self.refrescar()

    # ── Construcción ────────────────────────────────────────────────────────

    def _build_ui(self):
        # Scroll area — evita que el contenido se comprima en pantallas pequeñas
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        inner = QWidget()
        root = QVBoxLayout(inner)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(12)

        # Contenedor exterior sin scroll para occupar el espacio del widget
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        # ── Cabecera ─────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        title = QLabel("Dashboard")
        title.setStyleSheet(f"font-size:17px; font-weight:700; color:{_TEXT};")
        hdr.addWidget(title)
        hdr.addStretch()
        root.addLayout(hdr)

        # ── Banner de bienvenida (C1) — visible solo cuando no hay datos ─
        self._banner_vacio = QFrame()
        self._banner_vacio.setStyleSheet(
            f"QFrame {{ background:#dde8ed; border:1px solid #a8d0dc; "
            f"border-radius:10px; }}"
        )
        _bv = QHBoxLayout(self._banner_vacio)
        _bv.setContentsMargins(16, 12, 16, 12)
        _bv.setSpacing(14)
        _ico = QLabel("👋")
        _ico.setStyleSheet("font-size:22px; background:transparent; border:none;")
        _bv.addWidget(_ico)
        _msg = QLabel(
            "<b>Bienvenido a CONDORNEXUS.</b>  Para empezar, "
            "carga tu cartera en <b>📊 Cartera</b> o sincroniza desde <b>🔄 Nexo</b>."
        )
        _msg.setStyleSheet(f"font-size:13px; color:{_PINE}; background:transparent; border:none;")
        _msg.setTextFormat(Qt.RichText)
        _msg.setWordWrap(True)
        _bv.addWidget(_msg, 1)
        _btn_ir = QPushButton("Ir a Cartera →")
        _btn_ir.setStyleSheet(
            f"QPushButton {{ background:{_PINE}; color:#fff; border:none; "
            f"border-radius:6px; padding:6px 14px; font-size:12px; font-weight:600; }}"
            f"QPushButton:hover {{ background:#1d4f63; }}"
        )
        _btn_ir.clicked.connect(lambda: self.tab_request.emit(1))
        _bv.addWidget(_btn_ir)
        root.addWidget(self._banner_vacio)

        # ── Cards de métricas: grid 3×2 (mejor lectura en pantallas pequeñas) ─
        # Fila 0: métricas financieras  |  Fila 1: métricas de gestión
        cards_grid = QGridLayout()
        cards_grid.setSpacing(10)

        # on_click emite tab_request con el índice del tab destino (M5)
        # Tab 0=Dashboard, 1=Cartera, 2=Acciones, 3=Mensajes, 4=Nexo, 5=PDFs
        c1, self._m_vencido    = _card("Vencido",            "m_vencido",   _LOVE, lambda: self.tab_request.emit(1))
        c2, self._m_por_vencer = _card("Por vencer",         "m_pv",        _GOLD, lambda: self.tab_request.emit(1))
        c3, self._m_total      = _card("Total cartera",      "m_total",     _PINE, lambda: self.tab_request.emit(1))
        c4, self._m_enviados   = _card("Enviados hoy",       "m_env",       _FOAM, lambda: self.tab_request.emit(3))
        c5, self._m_riesgosos  = _card("Clientes riesgosos", "m_rie",       _LOVE, lambda: self.tab_request.emit(2))
        c6, self._m_acciones   = _card("Acciones pendientes","m_acc",       _IRIS, lambda: self.tab_request.emit(2))

        for c in (c1, c2, c3, c4, c5, c6):
            c.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # Fila financiera
        cards_grid.addWidget(c1, 0, 0)
        cards_grid.addWidget(c2, 0, 1)
        cards_grid.addWidget(c3, 0, 2)
        # Fila de gestión
        cards_grid.addWidget(c4, 1, 0)
        cards_grid.addWidget(c5, 1, 1)
        cards_grid.addWidget(c6, 1, 2)

        root.addLayout(cards_grid)

        # ── Acciones sugeridas ───────────────────────────────────────────
        acc_hdr = QHBoxLayout()
        acc_hdr.addWidget(_section_label("Acciones sugeridas hoy"))
        acc_hdr.addStretch()
        self._lbl_evaluado = QLabel("—")
        self._lbl_evaluado.setStyleSheet(
            f"color:{_MUTED}; font-size:11px; padding:3px 10px;"
        )
        acc_hdr.addWidget(self._lbl_evaluado)
        root.addLayout(acc_hdr)

        self._acciones_frame = QFrame()
        self._acciones_frame.setStyleSheet(
            f"QFrame {{ background:{_SURF}; border:1px solid #d6cec5; border-radius:10px; }}"
        )
        self._acciones_lay = QVBoxLayout(self._acciones_frame)
        self._acciones_lay.setContentsMargins(12, 10, 12, 10)
        self._acciones_lay.setSpacing(6)
        root.addWidget(self._acciones_frame)

        # ── Estadísticas de recuperación ─────────────────────────────────
        root.addWidget(_section_label("Recuperación mensual (últimos 6 meses)"))

        self._tabla_stats = QTableWidget(0, 4)
        self._tabla_stats.setHorizontalHeaderLabels(
            ["Mes", "Enviados", "Monto gestionado", "Actividad"]
        )
        self._tabla_stats.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self._tabla_stats.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._tabla_stats.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._tabla_stats.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._tabla_stats.setEditTriggers(QTableWidget.NoEditTriggers)
        self._tabla_stats.setSelectionMode(QTableWidget.NoSelection)
        self._tabla_stats.verticalHeader().setVisible(False)
        self._tabla_stats.setAlternatingRowColors(True)
        self._tabla_stats.setMaximumHeight(180)
        self._tabla_stats.setStyleSheet(
            f"QTableWidget {{ background:{_SURF}; border:1px solid #d6cec5; border-radius:8px; }}"
            f"QHeaderView::section {{ background:#ede5dc; color:{_MUTED}; font-size:12px; "
            f"font-weight:600; padding:6px 10px; border:none; }}"
            f"QTableWidget::item {{ padding:6px 10px; color:{_TEXT}; font-size:12px; }}"
            f"QTableWidget::item:alternate {{ background:#f5efe7; }}"
        )
        root.addWidget(self._tabla_stats)

        # ── Actividad reciente ───────────────────────────────────────────
        root.addWidget(_section_label("Actividad reciente"))

        self._tabla_actividad = QTableWidget(0, 5)
        self._tabla_actividad.setHorizontalHeaderLabels(
            ["Cliente", "Factura", "Canal", "Tipo", "Fecha"]
        )
        self._tabla_actividad.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._tabla_actividad.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._tabla_actividad.setEditTriggers(QTableWidget.NoEditTriggers)
        self._tabla_actividad.setSelectionBehavior(QTableWidget.SelectRows)
        self._tabla_actividad.setAlternatingRowColors(True)
        self._tabla_actividad.verticalHeader().setVisible(False)
        self._tabla_actividad.setMinimumHeight(160)
        self._tabla_actividad.setStyleSheet(
            f"QTableWidget {{ background:{_SURF}; border:1px solid #d6cec5; border-radius:8px; }}"
            f"QHeaderView::section {{ background:#ede5dc; color:{_MUTED}; font-size:12px; "
            f"font-weight:600; padding:6px 10px; border:none; }}"
            f"QTableWidget::item {{ padding:6px 10px; color:{_TEXT}; font-size:12px; }}"
            f"QTableWidget::item:alternate {{ background:#f5efe7; }}"
            f"QTableWidget::item:selected {{ background:#dde8ed; color:{_PINE}; }}"
        )
        root.addWidget(self._tabla_actividad)

        root.addStretch()
        scroll.setWidget(inner)

    # ── Datos ────────────────────────────────────────────────────────────────

    def refrescar(self):
        self._cargar_metricas()
        self._cargar_acciones()
        self._cargar_stats()
        self._cargar_actividad()
        from datetime import datetime
        self._lbl_evaluado.setText(
            f"Actualizado: {datetime.now().strftime('%H:%M')}"
        )
        # C1: mostrar banner solo cuando no hay datos cargados
        hay_datos = bool(db.get_facturas_cache())
        self._banner_vacio.setVisible(not hay_datos)

    def _cargar_metricas(self):
        facturas = db.get_facturas_cache()
        vencido  = sum(f.get("monto_pendiente", 0) for f in facturas if f.get("tipo") == "vencida")
        pv       = sum(f.get("monto_pendiente", 0) for f in facturas if f.get("tipo") == "por_vencer")
        total    = vencido + pv

        env_hoy  = db.get_enviados_hoy()
        scores   = db.get_todos_scores()
        riesgosos = sum(1 for s in scores if s.get("clasificacion") == "riesgoso")
        pendientes = db.get_acciones_pendientes(date.today().isoformat())

        self._m_vencido.setText(f"${vencido:,.2f}")
        self._m_por_vencer.setText(f"${pv:,.2f}")
        self._m_total.setText(f"${total:,.2f}")
        self._m_enviados.setText(str(len(env_hoy)))
        self._m_riesgosos.setText(str(riesgosos))
        self._m_acciones.setText(str(len(pendientes)))

    def _cargar_acciones(self):
        # Limpiar layout
        while self._acciones_lay.count():
            item = self._acciones_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        acciones = db.get_acciones_pendientes(date.today().isoformat())
        scores   = {s["cliente"]: s for s in db.get_todos_scores()}

        if not acciones:
            empty = QLabel("✅  Sin acciones pendientes para hoy")
            empty.setStyleSheet(f"font-size:13px; color:{_MUTED}; padding:10px;")
            empty.setAlignment(Qt.AlignCenter)
            self._acciones_lay.addWidget(empty)
            return

        _TIPO_ICON = {"contactar_email": "📧", "contactar_whatsapp": "💬", "revisar": "🔍"}
        _CLS_COLOR = {"confiable": _PINE, "medio": _GOLD, "riesgoso": _LOVE}

        for a in acciones[:6]:
            sc  = scores.get(a["cliente"], {})
            cls = sc.get("clasificacion", "medio")
            accent = _CLS_COLOR.get(cls, _GOLD)

            row = QFrame()
            # Borde izquierdo codificado por clasificación — elimina badge redundante
            row.setStyleSheet(
                f"QFrame {{"
                f"  background:{_SURF};"
                f"  border-top: 1px solid #d6cec5;"
                f"  border-right: 1px solid #d6cec5;"
                f"  border-bottom: 1px solid #d6cec5;"
                f"  border-left: 4px solid {accent};"
                f"  border-radius: 8px;"
                f"}}"
            )
            rl = QHBoxLayout(row)
            rl.setContentsMargins(10, 8, 10, 8)
            rl.setSpacing(8)

            icono = QLabel(_TIPO_ICON.get(a.get("tipo", ""), "🎯"))
            icono.setStyleSheet("font-size:16px; background:transparent; border:none;")
            icono.setFixedWidth(24)
            rl.addWidget(icono)

            info = QVBoxLayout()
            info.setSpacing(1)
            cliente_lbl = QLabel(a["cliente"])
            cliente_lbl.setStyleSheet(
                f"font-size:13px; font-weight:600; color:{_TEXT}; "
                f"background:transparent; border:none;"
            )
            cliente_lbl.setWordWrap(True)
            msg_text = a.get("mensaje_sugerido", "") or a.get("tipo", "")
            msg_lbl = QLabel(msg_text)
            msg_lbl.setStyleSheet(
                f"font-size:12px; color:{_MUTED}; background:transparent; border:none;"
            )
            msg_lbl.setWordWrap(True)
            info.addWidget(cliente_lbl)
            info.addWidget(msg_lbl)
            rl.addLayout(info, stretch=1)

            btn_ok = QPushButton("✓ Listo")
            btn_ok.setFixedWidth(72)
            btn_ok.setStyleSheet(
                f"QPushButton {{ background:{_PINE}; color:#fff; border:none; "
                f"border-radius:6px; padding:4px 8px; font-size:12px; min-height:28px; }}"
                f"QPushButton:hover {{ background:#1d4f63; }}"
            )
            accion_id = a["id"]
            btn_ok.clicked.connect(lambda _, aid=accion_id: self._completar(aid))
            rl.addWidget(btn_ok)

            self._acciones_lay.addWidget(row)

        if len(acciones) > 6:
            mas = QLabel(f"  … y {len(acciones) - 6} acciones más (ver pestaña Acciones)")
            mas.setStyleSheet(f"font-size:12px; color:{_MUTED}; padding:4px 10px;")
            self._acciones_lay.addWidget(mas)

    def _cargar_stats(self):
        stats = db.get_estadisticas_por_mes(meses=6)
        self._tabla_stats.setRowCount(len(stats))

        if not stats:
            self._tabla_stats.setRowCount(1)
            it = QTableWidgetItem("Sin registros de envíos todavía")
            it.setForeground(Qt.GlobalColor.gray)
            self._tabla_stats.setItem(0, 0, it)
            return

        max_n = max((r.get("n_enviados", 0) for r in stats), default=1) or 1

        for i, row in enumerate(stats):
            mes_raw = row.get("mes", "")
            try:
                y, m = mes_raw.split("-")
                from datetime import date
                mes_label = date(int(y), int(m), 1).strftime("%b %Y")
            except Exception:
                mes_label = mes_raw

            n       = row.get("n_enviados", 0)
            monto   = row.get("monto_gestionado", 0) or 0
            barras  = int(n / max_n * 20)
            barra   = "█" * barras + "░" * (20 - barras)

            self._tabla_stats.setItem(i, 0, _item(mes_label))
            self._tabla_stats.setItem(i, 1, _item(str(n)))
            self._tabla_stats.setItem(i, 2, _item(f"${monto:,.2f}"))
            it_barra = _item(f"{barra}  {int(n/max_n*100)}%")
            it_barra.setForeground(Qt.GlobalColor.darkCyan)
            self._tabla_stats.setItem(i, 3, it_barra)

    def _cargar_actividad(self):
        actividad = db.get_actividad_reciente(15)
        self._tabla_actividad.setRowCount(len(actividad))
        for i, m in enumerate(actividad):
            self._tabla_actividad.setItem(i, 0, _item(m.get("cliente", "")))
            self._tabla_actividad.setItem(i, 1, _item(m.get("factura_no", "—")))
            self._tabla_actividad.setItem(i, 2, _item(m.get("canal", "—")))
            self._tabla_actividad.setItem(i, 3, _item(m.get("tipo", "—")))
            fecha = (m.get("fecha") or "")[:16].replace("T", " ")
            self._tabla_actividad.setItem(i, 4, _item(fecha))

    # ── Eventos ──────────────────────────────────────────────────────────────

    def _completar(self, accion_id: int):
        db.completar_accion(accion_id)
        self.status_msg.emit("Acción marcada como completada")
        self._cargar_acciones()
        self._cargar_metricas()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"font-size:12px; font-weight:600; color:{_SUBTLE}; margin-bottom:2px;"
    )
    return lbl


def _item(text: str) -> QTableWidgetItem:
    item = QTableWidgetItem(str(text))
    item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
    return item
