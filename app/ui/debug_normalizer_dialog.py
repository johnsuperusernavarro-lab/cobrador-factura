"""
app/ui/debug_normalizer_dialog.py — Validación visual del normalizador de cartera

Muestra al usuario cómo se interpretaron los datos de su archivo ANTES de guardarlos.
Tres secciones: mapeo de columnas, vista previa de datos, advertencias detectadas.
El usuario confirma o cancela: ningún dato se persiste hasta confirmar.
"""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QAbstractItemView, QDialog, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QPushButton, QScrollArea, QSizePolicy, QTableWidget,
    QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from app.services.xls_normalizer import DetectionResult

# ── Paleta Rosé Pine Dawn ──────────────────────────────────────────────────────
_PINE   = "#286983"
_LOVE   = "#b4637a"
_GOLD   = "#ea9d34"
_FOAM   = "#56949f"
_TEXT   = "#575279"
_MUTED  = "#9893a5"
_SUBTLE = "#797593"
_BG     = "#faf4ed"
_SURF   = "#fffaf3"
_OVR    = "#f2e9e1"
_BORDER = "#d6cec5"

# ── Definición de campos ───────────────────────────────────────────────────────

# (campo_interno, etiqueta UI, es_requerido)
_CAMPOS = [
    ("cliente",           "Cliente / Razón social",    True),
    ("factura_no",        "N° de factura",             False),
    ("monto_pendiente",   "Saldo / Monto pendiente",   True),
    ("monto",             "Monto total",               False),
    ("fecha_vencimiento", "Fecha de vencimiento",      True),
    ("fecha_emision",     "Fecha de emisión",          False),
    ("descripcion",       "Descripción / Detalle",     False),
    ("email",             "Email del cliente",         False),
    ("telefono",          "Teléfono del cliente",      False),
    ("cedula_ruc",        "CI / RUC",                  False),
]

# (campo_interno, encabezado tabla, ancho_px)
_PREVIEW_COLS = [
    ("cliente",           "Cliente",          0),    # 0 = stretch
    ("factura_no",        "N° Factura",      95),
    ("monto_pendiente",   "Saldo",          105),
    ("fecha_vencimiento", "Fecha Vcto.",    105),
    ("tipo",              "Tipo",            90),
]

_BG_ANOMALIA_MONTO = "#fff8ec"   # fondo gold claro para saldo cero
_BG_ANOMALIA_FECHA = "#fdf0f2"   # fondo love claro para fecha vacía


# ── Diálogo principal ─────────────────────────────────────────────────────────

class DebugNormalizerDialog(QDialog):
    """
    Diálogo de validación visual del normalizador.
    Mostrar inmediatamente después de normalizar el archivo, antes de guardar en BD.
    """

    def __init__(self, result: DetectionResult, nombre_archivo: str, parent=None):
        super().__init__(parent)
        self._result = result
        self._nombre_archivo = nombre_archivo
        self._n_anomalias = self._contar_anomalias()
        self._score = self._calcular_score()

        self.setWindowTitle("Validar interpretación del archivo")
        self.setMinimumSize(840, 580)
        self.resize(980, 680)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setStyleSheet(f"QDialog {{ background: {_BG}; }}")

        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        root.addWidget(self._make_header())
        root.addWidget(self._make_tabs(), 1)
        root.addWidget(self._make_footer())

    # ── Score de confianza ─────────────────────────────────────────────────

    def _calcular_score(self) -> int:
        col_map    = self._result.col_map
        col_scores = self._result.col_scores

        score = 100

        # Campos críticos
        if "cliente" not in col_map:
            score -= 30
        if "monto_pendiente" not in col_map and "monto" not in col_map:
            score -= 25
        if "fecha_vencimiento" not in col_map:
            score -= 15

        # Penalidad por mapeos fuzzy de baja calidad
        for campo in col_map:
            if col_scores.get(campo, 100) < 85:
                score -= 3

        # Penalidad por advertencias (máx -15)
        score -= min(15, len(self._result.advertencias) * 3)

        # Penalidad por anomalías en datos (máx -10)
        score -= min(10, self._n_anomalias)

        return max(0, min(100, score))

    def _contar_anomalias(self) -> int:
        n = 0
        for f in self._result.facturas[:50]:
            if float(f.get("monto_pendiente") or 0) == 0:
                n += 1
            if not f.get("fecha_vencimiento"):
                n += 1
        return n

    def _score_color(self) -> str:
        if self._score >= 75:
            return _PINE
        elif self._score >= 50:
            return _GOLD
        return _LOVE

    def _score_label(self) -> str:
        if self._score >= 75:
            return "Bueno"
        elif self._score >= 50:
            return "Revisar"
        return "Atención"

    # ── Header ─────────────────────────────────────────────────────────────

    def _make_header(self) -> QFrame:
        header = QFrame()
        header.setStyleSheet(
            f"QFrame {{ background: {_SURF}; border: none; "
            f"border-bottom: 1px solid {_BORDER}; }}"
        )

        row = QHBoxLayout(header)
        row.setContentsMargins(24, 16, 24, 16)
        row.setSpacing(20)

        # Info izquierda
        left = QVBoxLayout()
        left.setSpacing(4)

        lbl_titulo = QLabel("Validar interpretación del archivo")
        lbl_titulo.setStyleSheet(
            f"font-size: 15px; font-weight: 700; color: {_TEXT}; "
            "background: transparent; border: none;"
        )

        n        = len(self._result.facturas)
        software = self._result.software
        archivo  = self._nombre_archivo

        lbl_sub = QLabel(
            f"<span style='color:{_MUTED};'>Archivo:</span> "
            f"<b style='color:{_TEXT};'>{archivo}</b>"
            f"&nbsp;&nbsp;·&nbsp;&nbsp;"
            f"<span style='color:{_MUTED};'>Software detectado:</span> "
            f"<b style='color:{_PINE};'>{software}</b>"
            f"&nbsp;&nbsp;·&nbsp;&nbsp;"
            f"<b style='color:{_TEXT};'>{n}</b>"
            f"<span style='color:{_MUTED};'> facturas encontradas</span>"
        )
        lbl_sub.setTextFormat(Qt.RichText)
        lbl_sub.setStyleSheet("background: transparent; border: none; font-size: 12px;")

        left.addWidget(lbl_titulo)
        left.addWidget(lbl_sub)
        row.addLayout(left, 1)

        # Badge de score derecha
        color = self._score_color()

        badge = QFrame()
        badge.setFixedSize(70, 70)
        badge.setStyleSheet(
            f"QFrame {{ background: {color}; border-radius: 35px; border: none; }}"
        )
        badge_lay = QVBoxLayout(badge)
        badge_lay.setContentsMargins(0, 0, 0, 0)
        badge_lay.setSpacing(0)

        lbl_pct = QLabel(f"{self._score}%")
        lbl_pct.setAlignment(Qt.AlignCenter)
        lbl_pct.setStyleSheet(
            "color: white; font-size: 17px; font-weight: 800; "
            "background: transparent; border: none;"
        )
        badge_lay.addWidget(lbl_pct, 0, Qt.AlignCenter)

        right_col = QVBoxLayout()
        right_col.setSpacing(4)
        right_col.setAlignment(Qt.AlignCenter)
        right_col.addWidget(badge, 0, Qt.AlignCenter)

        lbl_quality = QLabel(self._score_label())
        lbl_quality.setAlignment(Qt.AlignCenter)
        lbl_quality.setStyleSheet(
            f"color: {color}; font-size: 11px; font-weight: 600; "
            "background: transparent; border: none;"
        )
        right_col.addWidget(lbl_quality, 0, Qt.AlignCenter)

        row.addLayout(right_col)
        return header

    # ── Tabs ───────────────────────────────────────────────────────────────

    def _make_tabs(self) -> QTabWidget:
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.setStyleSheet(
            f"QTabWidget::pane {{ border: none; background: {_BG}; }}"
            f"QTabBar::tab {{ background: {_OVR}; color: {_MUTED}; "
            "padding: 9px 20px; font-size: 12px; border: none; margin-right: 2px; }}"
            f"QTabBar::tab:selected {{ background: {_BG}; color: {_TEXT}; font-weight: 600; }}"
            f"QTabBar::tab:hover {{ background: {_BG}; }}"
        )

        n_warn    = len(self._result.advertencias)
        n_preview = min(50, len(self._result.facturas))

        lbl_mapeo = "🧠  Mapeo de columnas"
        lbl_prev  = f"📊  Vista previa  ({n_preview})"
        if self._n_anomalias:
            lbl_prev += f"  · ⚠ {self._n_anomalias}"
        lbl_warn  = f"⚠  Advertencias  ({n_warn})" if n_warn else "⚠  Advertencias"

        tabs.addTab(self._make_tab_mapeo(),        lbl_mapeo)
        tabs.addTab(self._make_tab_preview(),       lbl_prev)
        tabs.addTab(self._make_tab_advertencias(),  lbl_warn)

        # Abrir la pestaña más relevante
        if self._score < 50 and n_warn > 0:
            tabs.setCurrentIndex(2)
        elif self._n_anomalias > 5:
            tabs.setCurrentIndex(1)

        return tabs

    # ── Tab: Mapeo ─────────────────────────────────────────────────────────

    def _make_tab_mapeo(self) -> QWidget:
        widget = QWidget()
        widget.setStyleSheet(f"background: {_BG};")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(10)

        col_map    = self._result.col_map
        col_scores = self._result.col_scores
        headers    = self._result.headers
        hay_headers = bool(headers)

        desc = QLabel(
            "Así interpretó el sistema los encabezados de tu archivo. "
            "Los campos marcados con <b>*</b> son necesarios para el funcionamiento correcto."
        )
        desc.setWordWrap(True)
        desc.setTextFormat(Qt.RichText)
        desc.setStyleSheet(
            f"color: {_MUTED}; font-size: 12px; background: transparent; border: none;"
        )
        layout.addWidget(desc)

        tbl = QTableWidget()
        tbl.setColumnCount(3)
        tbl.setHorizontalHeaderLabels(
            ["Campo del sistema", "Columna encontrada en tu archivo", "Confianza del mapeo"]
        )
        tbl.setRowCount(len(_CAMPOS))
        tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tbl.setSelectionMode(QAbstractItemView.SingleSelection)
        tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        tbl.verticalHeader().setVisible(False)
        tbl.setShowGrid(False)
        tbl.setStyleSheet(
            f"QTableWidget {{ background: {_SURF}; border: 1px solid {_BORDER}; "
            "border-radius: 8px; font-size: 12px; }}"
            f"QTableWidget::item {{ padding: 6px 12px; color: {_TEXT}; "
            f"border-bottom: 1px solid {_OVR}; }}"
            f"QTableWidget::item:selected {{ background: #dde8ed; color: {_PINE}; }}"
            f"QHeaderView::section {{ background: {_OVR}; color: {_SUBTLE}; "
            "font-size: 11px; font-weight: 600; padding: 8px 12px; "
            f"border: none; border-bottom: 1px solid {_BORDER}; }}"
        )

        for row_i, (campo, label, required) in enumerate(_CAMPOS):
            # Columna 0: Campo del sistema
            lbl_campo = label + ("  *" if required else "")
            item0 = QTableWidgetItem(lbl_campo)
            if required:
                f = QFont()
                f.setBold(True)
                item0.setFont(f)
            item0.setForeground(QColor(_TEXT))
            tbl.setItem(row_i, 0, item0)

            # Columna 1: Header original en el archivo
            if campo in col_map:
                idx = col_map[campo]
                header_orig = headers[idx] if idx < len(headers) else f"Columna {idx}"
                item1 = QTableWidgetItem(f'"{header_orig}"')
                item1.setForeground(QColor(_TEXT))
            else:
                item1 = QTableWidgetItem("— No encontrado —")
                item1.setForeground(QColor(_LOVE if required else _MUTED))
            tbl.setItem(row_i, 1, item1)

            # Columna 2: Confianza
            if not hay_headers:
                conf_text  = "N/A — formato nativo detectado"
                conf_color = _MUTED
                bg_conf    = None
            elif campo in col_map:
                s = col_scores.get(campo, 100)
                if s >= 90:
                    conf_text  = f"✓  Exacto  ({s}%)"
                    conf_color = _PINE
                    bg_conf    = None
                elif s >= 80:
                    conf_text  = f"✓  Bueno  ({s}%)"
                    conf_color = _FOAM
                    bg_conf    = None
                else:
                    conf_text  = f"⚠  Marginal  ({s}%) — revisa"
                    conf_color = _GOLD
                    bg_conf    = "#fff8ec"
            else:
                s = col_scores.get(campo, 0)
                if s > 0:
                    conf_text  = f"✗  Mejor coincidencia: {s}%  (bajo umbral)"
                else:
                    conf_text  = "✗  Sin coincidencia en el archivo"
                conf_color = _LOVE if required else _MUTED
                bg_conf    = "#fdf0f2" if required else None

            item2 = QTableWidgetItem(conf_text)
            item2.setForeground(QColor(conf_color))
            if bg_conf:
                item2.setBackground(QColor(bg_conf))
            tbl.setItem(row_i, 2, item2)

            tbl.setRowHeight(row_i, 36)

        hdr = tbl.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)

        layout.addWidget(tbl, 1)

        # Leyenda
        ley = QHBoxLayout()
        ley.setSpacing(16)
        for color, texto in [
            (_PINE, "✓ Exacto / Bueno (≥ 80%)"),
            (_GOLD, "⚠ Marginal (72–79%)"),
            (_LOVE, "✗ No encontrado (requerido)"),
            (_MUTED, "✗ No encontrado (opcional)"),
        ]:
            lbl = QLabel(f'<span style="color:{color}; font-size:11px;">{texto}</span>')
            lbl.setTextFormat(Qt.RichText)
            lbl.setStyleSheet("background: transparent; border: none;")
            ley.addWidget(lbl)
        ley.addStretch()
        layout.addLayout(ley)

        return widget

    # ── Tab: Vista previa ──────────────────────────────────────────────────

    def _make_tab_preview(self) -> QWidget:
        widget = QWidget()
        widget.setStyleSheet(f"background: {_BG};")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(10)

        facturas  = self._result.facturas[:50]
        n_total   = len(self._result.facturas)

        desc_text = (
            f"Mostrando las primeras <b>{len(facturas)}</b> de <b>{n_total}</b> "
            "facturas tal como quedarán en el sistema."
        )
        if self._n_anomalias:
            desc_text += (
                f"  Se detectaron <b style='color:{_LOVE};'>{self._n_anomalias} "
                f"valor(es) anómalos</b> resaltados."
            )
        desc = QLabel(desc_text)
        desc.setWordWrap(True)
        desc.setTextFormat(Qt.RichText)
        desc.setStyleSheet(
            f"color: {_MUTED}; font-size: 12px; background: transparent; border: none;"
        )
        layout.addWidget(desc)

        tbl = QTableWidget()
        tbl.setColumnCount(len(_PREVIEW_COLS))
        tbl.setHorizontalHeaderLabels([c[1] for c in _PREVIEW_COLS])
        tbl.setRowCount(len(facturas))
        tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tbl.setSelectionMode(QAbstractItemView.SingleSelection)
        tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        tbl.setAlternatingRowColors(True)
        tbl.verticalHeader().setVisible(False)
        tbl.setShowGrid(False)
        tbl.setStyleSheet(
            f"QTableWidget {{ background: {_SURF}; "
            f"alternate-background-color: {_OVR}; "
            f"border: 1px solid {_BORDER}; border-radius: 8px; font-size: 12px; }}"
            f"QTableWidget::item {{ padding: 4px 8px; color: {_TEXT}; }}"
            f"QTableWidget::item:selected {{ background: #dde8ed; color: {_PINE}; }}"
            f"QHeaderView::section {{ background: {_OVR}; color: {_SUBTLE}; "
            "font-size: 11px; font-weight: 600; padding: 6px 8px; "
            f"border: none; border-bottom: 1px solid {_BORDER}; }}"
        )

        for row_i, f in enumerate(facturas):
            for col_i, (campo, _lbl, _w) in enumerate(_PREVIEW_COLS):
                val = f.get(campo, "")

                if campo == "monto_pendiente":
                    text = f"${float(val or 0):,.2f}"
                elif campo == "tipo":
                    text = "🔴 Vencida" if val == "vencida" else "🔵 Por vencer"
                else:
                    text = str(val) if val else "—"

                item = QTableWidgetItem(text)

                # Alineación
                if campo == "monto_pendiente":
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                elif campo in ("factura_no", "tipo"):
                    item.setTextAlignment(Qt.AlignCenter)

                # Resaltar anomalías
                if campo == "monto_pendiente" and float(val or 0) == 0:
                    item.setBackground(QColor(_BG_ANOMALIA_MONTO))
                    item.setToolTip(
                        "⚠ Saldo cero — esta fila podría estar ya pagada "
                        "o tener un error en la columna de saldo"
                    )
                elif campo == "fecha_vencimiento" and not val:
                    item.setBackground(QColor(_BG_ANOMALIA_FECHA))
                    item.setToolTip(
                        "⚠ Fecha de vencimiento vacía — "
                        "no se podrá calcular antigüedad ni enviar recordatorios automáticos"
                    )

                tbl.setItem(row_i, col_i, item)
            tbl.setRowHeight(row_i, 28)

        hdr = tbl.horizontalHeader()
        for col_i, (_, _lbl, w) in enumerate(_PREVIEW_COLS):
            if w == 0:
                hdr.setSectionResizeMode(col_i, QHeaderView.Stretch)
            else:
                hdr.setSectionResizeMode(col_i, QHeaderView.Fixed)
                tbl.setColumnWidth(col_i, w)

        layout.addWidget(tbl, 1)

        # Leyenda de colores
        ley = QHBoxLayout()
        ley.setSpacing(16)
        for bg, texto in [
            (_BG_ANOMALIA_MONTO, "Saldo cero"),
            (_BG_ANOMALIA_FECHA, "Fecha de vencimiento vacía"),
        ]:
            dot = QFrame()
            dot.setFixedSize(12, 12)
            dot.setStyleSheet(
                f"background: {bg}; border: 1px solid {_BORDER}; border-radius: 2px;"
            )
            lbl = QLabel(texto)
            lbl.setStyleSheet(
                f"color: {_MUTED}; font-size: 11px; background: transparent; border: none;"
            )
            sub = QHBoxLayout()
            sub.setSpacing(5)
            sub.setContentsMargins(0, 0, 0, 0)
            sub.addWidget(dot)
            sub.addWidget(lbl)
            ley.addLayout(sub)
        ley.addStretch()
        layout.addLayout(ley)

        return widget

    # ── Tab: Advertencias ──────────────────────────────────────────────────

    def _make_tab_advertencias(self) -> QWidget:
        widget = QWidget()
        widget.setStyleSheet(f"background: {_BG};")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(12)

        advertencias = self._result.advertencias

        if not advertencias:
            lbl = QLabel(
                "✓  No se detectaron advertencias.\n"
                "El archivo se interpretó limpiamente."
            )
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(
                f"color: {_PINE}; font-size: 13px; background: transparent; border: none;"
            )
            layout.addWidget(lbl, 1, Qt.AlignCenter)
            return widget

        # Resumen
        desc = QLabel(
            f"Se omitieron <b>{len(advertencias)}</b> fila(s) con problemas. "
            "El resto de los datos se cargará normalmente."
        )
        desc.setWordWrap(True)
        desc.setTextFormat(Qt.RichText)
        desc.setStyleSheet(
            f"color: {_MUTED}; font-size: 12px; background: transparent; border: none;"
        )
        layout.addWidget(desc)

        # Cards de resumen por categoría
        grupos: dict[str, int] = {}
        for w in advertencias:
            cat = w.split(":")[0].strip() if ":" in w else w[:45]
            grupos[cat] = grupos.get(cat, 0) + 1

        cards_row = QHBoxLayout()
        cards_row.setSpacing(8)
        for cat, count in list(grupos.items())[:4]:
            card = QFrame()
            card.setStyleSheet(
                f"QFrame {{ background: {_SURF}; border: 1px solid {_BORDER}; "
                "border-radius: 8px; }}"
            )
            card_lay = QVBoxLayout(card)
            card_lay.setContentsMargins(14, 10, 14, 10)
            card_lay.setSpacing(2)

            lbl_n = QLabel(str(count))
            lbl_n.setStyleSheet(
                f"font-size: 22px; font-weight: 800; color: {_GOLD}; "
                "background: transparent; border: none;"
            )
            lbl_cat = QLabel(cat)
            lbl_cat.setWordWrap(True)
            lbl_cat.setStyleSheet(
                f"font-size: 11px; color: {_MUTED}; background: transparent; border: none;"
            )
            card_lay.addWidget(lbl_n)
            card_lay.addWidget(lbl_cat)
            cards_row.addWidget(card)
        cards_row.addStretch()
        layout.addLayout(cards_row)

        # Lista completa en scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea {{ border: 1px solid {_BORDER}; border-radius: 8px; "
            f"background: {_SURF}; }}"
        )

        inner = QWidget()
        inner.setStyleSheet(f"background: {_SURF};")
        inner_lay = QVBoxLayout(inner)
        inner_lay.setContentsMargins(14, 8, 14, 8)
        inner_lay.setSpacing(0)

        for warn in advertencias:
            row_frame = QFrame()
            row_frame.setStyleSheet(
                f"background: transparent; border: none; "
                f"border-bottom: 1px solid {_OVR};"
            )
            row_lay = QHBoxLayout(row_frame)
            row_lay.setContentsMargins(0, 6, 0, 6)
            row_lay.setSpacing(10)

            icon = QLabel("⚠")
            icon.setFixedWidth(16)
            icon.setStyleSheet(
                f"color: {_GOLD}; background: transparent; border: none; font-size: 12px;"
            )

            warn_lbl = QLabel(warn)
            warn_lbl.setWordWrap(True)
            warn_lbl.setStyleSheet(
                f"color: {_TEXT}; font-size: 12px; background: transparent; border: none;"
            )

            row_lay.addWidget(icon)
            row_lay.addWidget(warn_lbl, 1)
            inner_lay.addWidget(row_frame)

        inner_lay.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll, 1)

        return widget

    # ── Footer ─────────────────────────────────────────────────────────────

    def _make_footer(self) -> QFrame:
        footer = QFrame()
        footer.setStyleSheet(
            f"QFrame {{ background: {_SURF}; border: none; "
            f"border-top: 1px solid {_BORDER}; }}"
        )

        row = QHBoxLayout(footer)
        row.setContentsMargins(24, 12, 24, 12)
        row.setSpacing(12)

        n_warn = len(self._result.advertencias)
        if n_warn or self._n_anomalias:
            parts = []
            if n_warn:
                parts.append(f"{n_warn} fila(s) omitida(s)")
            if self._n_anomalias:
                parts.append(f"{self._n_anomalias} valor(es) anómalo(s)")
            note = QLabel(
                f"⚠  {' · '.join(parts)}. Revisa las pestañas antes de confirmar."
            )
            note.setStyleSheet(
                f"color: {_GOLD}; font-size: 12px; background: transparent; border: none;"
            )
            row.addWidget(note, 1)
        else:
            lbl_ok = QLabel("✓  Archivo interpretado correctamente. Listo para cargar.")
            lbl_ok.setStyleSheet(
                f"color: {_PINE}; font-size: 12px; background: transparent; border: none;"
            )
            row.addWidget(lbl_ok, 1)

        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.setFixedHeight(36)
        btn_cancelar.setMinimumWidth(100)
        btn_cancelar.setStyleSheet(
            f"QPushButton {{ background: {_OVR}; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 6px; "
            "padding: 0 18px; font-size: 13px; }}"
            f"QPushButton:hover {{ background: {_BORDER}; }}"
        )
        btn_cancelar.clicked.connect(self.reject)

        btn_confirmar = QPushButton("Confirmar y cargar  →")
        btn_confirmar.setFixedHeight(36)
        btn_confirmar.setMinimumWidth(170)
        btn_confirmar.setDefault(True)
        btn_confirmar.setStyleSheet(
            f"QPushButton {{ background: {_PINE}; color: white; border: none; "
            "border-radius: 6px; padding: 0 22px; "
            "font-size: 13px; font-weight: 600; }}"
            "QPushButton:hover { background: #1e5470; }"
            "QPushButton:pressed { background: #164060; }"
        )
        btn_confirmar.clicked.connect(self.accept)

        row.addWidget(btn_cancelar)
        row.addWidget(btn_confirmar)

        return footer
