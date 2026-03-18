"""
ui/cotizaciones_widget.py — Tab 💼 Cotizaciones

Módulo de pre-facturación: crea, gestiona y envía cotizaciones.
Integrado con contactos existentes (cliente híbrido) y con el flujo de cobranza.
"""

import webbrowser
from datetime import date, datetime, timedelta

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QDialog, QTextEdit, QComboBox, QAbstractItemView,
    QLineEdit, QStackedWidget,
)

import core.database as db
from core.cotizaciones import generar_mensaje_cotizacion, generar_url_whatsapp
from ui.cotizacion_form_dialog import CotizacionFormDialog

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

_ESTADO_COLOR = {
    "pendiente": _GOLD,
    "enviada":   _FOAM,
    "aceptada":  _PINE,
    "rechazada": _LOVE,
}
_ESTADO_LABEL = {
    "pendiente": "⏳ Pendiente",
    "enviada":   "📤 Enviada",
    "aceptada":  "✅ Aceptada",
    "rechazada": "❌ Rechazada",
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _btn(color: str, text_color: str = "white") -> str:
    return (
        f"QPushButton {{ background:{color}; color:{text_color}; font-weight:600; "
        f"font-size:12px; border-radius:6px; padding:5px 14px; border:none; }}"
        f"QPushButton:hover {{ background:{color}dd; }}"
        f"QPushButton:disabled {{ background:#d6cec5; color:#a8a0a0; }}"
    )


def _pill(color: str, active: bool) -> str:
    bg = color if active else "transparent"
    fg = "white" if active else color
    return (
        f"QPushButton {{ background:{bg}; color:{fg}; font-size:11px; font-weight:600; "
        f"border:1px solid {color}; border-radius:10px; padding:3px 12px; }}"
        f"QPushButton:hover {{ background:{color}; color:white; }}"
    )


def _lbl(texto: str, bold: bool = False, size: int = 12, color: str = _TEXT) -> QLabel:
    lbl = QLabel(texto)
    style = f"color:{color}; font-size:{size}px;"
    if bold:
        style += " font-weight:700;"
    lbl.setStyleSheet(style)
    return lbl


def _fmt_fecha(raw: str) -> str:
    try:
        return datetime.fromisoformat(raw[:10]).strftime("%d/%m/%Y")
    except Exception:
        return raw[:10] if raw else "—"


def _calcular_vence(creada_en: str, validez_dias: int, estado: str) -> tuple[str, str]:
    """Retorna (texto, color) para la columna Vencimiento."""
    if estado in ("aceptada", "rechazada"):
        return "—", _MUTED
    try:
        fecha_creacion = datetime.fromisoformat(creada_en[:10]).date()
        fecha_vence    = fecha_creacion + timedelta(days=validez_dias)
        hoy            = date.today()
        diff           = (fecha_vence - hoy).days
        if diff < 0:
            return f"Venció hace {-diff}d", _LOVE
        elif diff == 0:
            return "Vence hoy", _LOVE
        elif diff <= 5:
            return f"Vence en {diff}d", _GOLD
        else:
            return fecha_vence.strftime("%d/%m/%Y"), _TEXT
    except Exception:
        return f"{validez_dias}d", _MUTED


# ─── Widget principal ─────────────────────────────────────────────────────────

class CotizacionesWidget(QWidget):

    status_msg = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._filtro_estado: str | None = None
        self._cotizaciones: list[dict] = []
        self._build_ui()
        self.refrescar()

    # ── Construcción ─────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        # ── Cabecera ──────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        title = QLabel("Cotizaciones")
        title.setStyleSheet(f"font-size:17px; font-weight:700; color:{_TEXT};")
        hdr.addWidget(title)
        hdr.addStretch()

        self._search = QLineEdit()
        self._search.setPlaceholderText("Buscar por cliente…")
        self._search.setClearButtonEnabled(True)
        self._search.setFixedWidth(210)
        self._search.setStyleSheet(
            f"QLineEdit {{ border:1px solid #d6cec5; border-radius:6px; "
            f"padding:4px 8px; font-size:12px; background:{_SURF}; }}"
            f"QLineEdit:focus {{ border-color:{_PINE}; }}"
        )
        self._search.textChanged.connect(self._aplicar_filtro_texto)
        hdr.addWidget(self._search)

        self._btn_nueva = QPushButton("＋  Nueva cotización")
        self._btn_nueva.setStyleSheet(_btn(_PINE))
        self._btn_nueva.clicked.connect(self._nueva_cotizacion)
        hdr.addWidget(self._btn_nueva)

        root.addLayout(hdr)

        # ── Pills de estado (con conteos) ─────────────────────────────────
        pills_row = QHBoxLayout()
        pills_row.setSpacing(6)

        self._pills: list[QPushButton] = []
        self._pills_estados = [None, "pendiente", "enviada", "aceptada", "rechazada"]
        self._pills_colores  = [_SUBTLE, _GOLD, _FOAM, _PINE, _LOVE]
        self._pills_base     = ["Todas", "Pendiente", "Enviada", "Aceptada", "Rechazada"]

        for label, estado, color in zip(
            self._pills_base, self._pills_estados, self._pills_colores
        ):
            btn = QPushButton(label)
            btn.setStyleSheet(_pill(color, estado == self._filtro_estado))
            btn.clicked.connect(
                lambda _, e=estado, c=color: self._set_filtro(e, c)
            )
            self._pills.append(btn)
            pills_row.addWidget(btn)

        pills_row.addStretch()
        root.addLayout(pills_row)

        # ── Stack: empty state (0) ↔ contenido (1) ───────────────────────
        self._stack = QStackedWidget()

        # Página 0 — Estado vacío
        self._stack.addWidget(self._build_empty_state())

        # Página 1 — Tabla + barra de acciones
        self._stack.addWidget(self._build_contenido())

        root.addWidget(self._stack)

    def _build_empty_state(self) -> QWidget:
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background:{_SURF}; border:1px dashed #d6cec5; border-radius:12px; }}"
        )
        lay = QVBoxLayout(frame)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(14)
        lay.setContentsMargins(40, 50, 40, 50)

        ico = QLabel("📋")
        ico.setAlignment(Qt.AlignCenter)
        ico.setStyleSheet("font-size:48px; border:none; background:transparent;")
        lay.addWidget(ico)

        titulo = QLabel("Aún no tienes cotizaciones")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet(
            f"font-size:16px; font-weight:700; color:{_TEXT}; "
            f"border:none; background:transparent;"
        )
        lay.addWidget(titulo)

        desc = QLabel(
            "Las cotizaciones te permiten presentar presupuestos a tus clientes\n"
            "antes de emitir una factura. Crea una en menos de un minuto."
        )
        desc.setAlignment(Qt.AlignCenter)
        desc.setStyleSheet(
            f"font-size:12px; color:{_MUTED}; border:none; background:transparent;"
        )
        lay.addWidget(desc)

        lay.addSpacing(8)

        btn_cta = QPushButton("＋  Crear primera cotización")
        btn_cta.setStyleSheet(_btn(_PINE))
        btn_cta.setFixedWidth(220)
        btn_cta.clicked.connect(self._nueva_cotizacion)

        cta_row = QHBoxLayout()
        cta_row.addStretch()
        cta_row.addWidget(btn_cta)
        cta_row.addStretch()
        lay.addLayout(cta_row)

        return frame

    def _build_contenido(self) -> QWidget:
        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        # Tabla
        self._tabla = QTableWidget(0, 5)
        self._tabla.setHorizontalHeaderLabels(
            ["N°", "Cliente", "Total", "Estado", "Vence"]
        )
        hdr = self._tabla.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._tabla.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tabla.setAlternatingRowColors(True)
        self._tabla.verticalHeader().setVisible(False)
        self._tabla.setToolTip("Doble clic sobre una fila para editarla")
        self._tabla.setStyleSheet(
            f"QTableWidget {{ border:1px solid #d6cec5; border-radius:8px; "
            f"background:{_SURF}; font-size:12px; color:{_TEXT}; }}"
            f"QTableWidget::item {{ padding:6px; }}"
            f"QHeaderView::section {{ background:{_OVR}; color:{_TEXT}; "
            f"font-weight:600; padding:6px; border:none; }}"
        )
        self._tabla.doubleClicked.connect(self._editar_seleccionada)
        self._tabla.itemSelectionChanged.connect(self._on_seleccion_cambio)
        lay.addWidget(self._tabla)

        # Barra de acciones
        acc_row = QHBoxLayout()
        acc_row.setSpacing(6)

        self._btn_editar = QPushButton("✏  Editar")
        self._btn_editar.setStyleSheet(_btn(_FOAM))
        self._btn_editar.setToolTip("Editar cotización seleccionada (también doble clic)")
        self._btn_editar.clicked.connect(self._editar_seleccionada)
        acc_row.addWidget(self._btn_editar)

        self._btn_enviar = QPushButton("📤  Enviar")
        self._btn_enviar.setStyleSheet(_btn(_PINE))
        self._btn_enviar.setToolTip("Enviar por email (copia) o WhatsApp")
        self._btn_enviar.clicked.connect(self._enviar_seleccionada)
        acc_row.addWidget(self._btn_enviar)

        self._btn_duplicar = QPushButton("⧉  Duplicar")
        self._btn_duplicar.setStyleSheet(_btn(_SUBTLE))
        self._btn_duplicar.setToolTip("Crea una copia en estado Pendiente")
        self._btn_duplicar.clicked.connect(self._duplicar_seleccionada)
        acc_row.addWidget(self._btn_duplicar)

        self._btn_estado = QPushButton("🔄  Cambiar estado")
        self._btn_estado.setStyleSheet(_btn(_GOLD))
        self._btn_estado.clicked.connect(self._cambiar_estado)
        acc_row.addWidget(self._btn_estado)

        self._btn_convertir = QPushButton("💸  Convertir a cobro")
        self._btn_convertir.setStyleSheet(_btn(_SUBTLE))
        self._btn_convertir.setToolTip(
            "Genera una acción de seguimiento en el tab 🎯 Acciones.\n"
            "Solo disponible para cotizaciones Enviadas o Aceptadas."
        )
        self._btn_convertir.clicked.connect(self._convertir_a_accion)
        acc_row.addWidget(self._btn_convertir)

        acc_row.addStretch()

        self._btn_eliminar = QPushButton("🗑  Eliminar")
        self._btn_eliminar.setStyleSheet(_btn(_LOVE))
        self._btn_eliminar.clicked.connect(self._eliminar_seleccionada)
        acc_row.addWidget(self._btn_eliminar)

        lay.addLayout(acc_row)

        # Todos los botones de acción empiezan deshabilitados
        self._set_botones_accion(False)

        return container

    # ── Estado de selección ───────────────────────────────────────────────────

    def _on_seleccion_cambio(self):
        tiene = bool(self._tabla.selectedItems())
        self._set_botones_accion(tiene)

    def _set_botones_accion(self, habilitados: bool):
        for btn in (
            self._btn_editar, self._btn_enviar, self._btn_duplicar,
            self._btn_estado, self._btn_convertir, self._btn_eliminar,
        ):
            btn.setEnabled(habilitados)

    # ── Filtros ───────────────────────────────────────────────────────────────

    def _set_filtro(self, estado: str | None, color: str):
        self._filtro_estado = estado
        colores = self._pills_colores
        estados = self._pills_estados
        for btn, e, c in zip(self._pills, estados, colores):
            btn.setStyleSheet(_pill(c, e == estado))
        self.refrescar()

    def _aplicar_filtro_texto(self, texto: str):
        texto = texto.lower()
        visible_count = 0
        for r in range(self._tabla.rowCount()):
            cliente_item = self._tabla.item(r, 1)
            ok = (not texto) or (cliente_item and texto in cliente_item.text().lower())
            self._tabla.setRowHidden(r, not ok)
            if ok:
                visible_count += 1
        if texto and visible_count == 0:
            self.status_msg.emit(f"Sin resultados para «{texto}»")
        elif texto:
            self.status_msg.emit(f"{visible_count} cotización(es) encontrada(s)")

    # ── Refresco ──────────────────────────────────────────────────────────────

    def refrescar(self):
        todas = db.get_cotizaciones(None)  # para conteos en pills
        self._actualizar_pills(todas)

        self._cotizaciones = db.get_cotizaciones(self._filtro_estado)
        self._poblar_tabla(self._cotizaciones)

        n = len(self._cotizaciones)
        sufijo = "es" if n != 1 else ""
        self.status_msg.emit(f"{n} cotización{sufijo}")

    def _actualizar_pills(self, todas: list[dict]):
        conteos: dict[str | None, int] = {None: len(todas)}
        for c in todas:
            e = c.get("estado", "pendiente")
            conteos[e] = conteos.get(e, 0) + 1

        for btn, base, estado in zip(self._pills, self._pills_base, self._pills_estados):
            n = conteos.get(estado, 0)
            btn.setText(f"{base}  {n}" if n else base)

    def _poblar_tabla(self, cotizaciones: list[dict]):
        self._tabla.blockSignals(True)
        self._tabla.setRowCount(0)

        for cot in cotizaciones:
            row   = self._tabla.rowCount()
            self._tabla.insertRow(row)

            cot_id  = cot.get("id", "")
            cliente = cot.get("cliente", "")
            estado  = cot.get("estado", "pendiente")
            total   = float(cot.get("total") or 0)
            color   = _ESTADO_COLOR.get(estado, _MUTED)
            label   = _ESTADO_LABEL.get(estado, estado)
            fecha_raw = cot.get("creada_en") or ""
            validez   = int(cot.get("validez_dias") or 30)

            vence_txt, vence_color = _calcular_vence(fecha_raw, validez, estado)

            # N°
            num_item = QTableWidgetItem(f"COT-{cot_id}")
            num_item.setForeground(QColor(_MUTED))
            num_item.setData(Qt.UserRole, cot_id)
            self._tabla.setItem(row, 0, num_item)

            # Cliente
            self._tabla.setItem(row, 1, QTableWidgetItem(cliente))

            # Total
            total_item = QTableWidgetItem(f"${total:,.2f}")
            total_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._tabla.setItem(row, 2, total_item)

            # Estado
            estado_item = QTableWidgetItem(label)
            estado_item.setForeground(QColor(color))
            estado_item.setTextAlignment(Qt.AlignCenter)
            self._tabla.setItem(row, 3, estado_item)

            # Vence
            vence_item = QTableWidgetItem(vence_txt)
            vence_item.setForeground(QColor(vence_color))
            self._tabla.setItem(row, 4, vence_item)

        self._tabla.blockSignals(False)

        # Mostrar empty-state o tabla
        self._stack.setCurrentIndex(0 if not cotizaciones else 1)
        self._set_botones_accion(False)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _fila_seleccionada(self) -> int | None:
        row = self._tabla.currentRow()
        if row < 0:
            return None
        item = self._tabla.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def _cotizacion_por_id(self, cot_id: int) -> dict | None:
        return next((c for c in self._cotizaciones if c.get("id") == cot_id), None)

    # ── Acciones ─────────────────────────────────────────────────────────────

    def _nueva_cotizacion(self):
        dlg = CotizacionFormDialog(parent=self)
        if dlg.exec_() == QDialog.Accepted:
            self.refrescar()
            self.status_msg.emit("Cotización creada. ¡Lista para enviar!")

    def _editar_seleccionada(self):
        cot_id = self._fila_seleccionada()
        if cot_id is None:
            return
        dlg = CotizacionFormDialog(cotizacion_id=cot_id, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            self.refrescar()
            self.status_msg.emit("Cotización actualizada.")

    def _enviar_seleccionada(self):
        cot_id = self._fila_seleccionada()
        if cot_id is None:
            return
        cot   = db.get_cotizacion(cot_id)
        items = db.get_items_cotizacion(cot_id)
        if not cot:
            return
        dlg = _EnviarCotizacionDialog(cot, items, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            db.actualizar_estado_cotizacion(cot_id, "enviada")
            db.registrar_mensaje_log(
                cot.get("cliente", ""), f"COT-{cot_id}",
                "cotizacion", dlg.canal_usado(), dlg.mensaje_usado(), "manual",
            )
            self.refrescar()
            self.status_msg.emit("Cotización enviada y marcada como 'Enviada'.")

    def _duplicar_seleccionada(self):
        cot_id = self._fila_seleccionada()
        if cot_id is None:
            return
        cot   = db.get_cotizacion(cot_id)
        items = db.get_items_cotizacion(cot_id)
        if not cot:
            return
        nuevo_id = db.crear_cotizacion(
            cliente      = cot.get("cliente", ""),
            contacto_id  = cot.get("contacto_id"),
            email        = cot.get("email") or "",
            telefono     = cot.get("telefono") or "",
            validez_dias = int(cot.get("validez_dias") or 30),
            notas        = cot.get("notas") or "",
            items        = [
                {
                    "descripcion": i.get("descripcion", ""),
                    "cantidad":    i.get("cantidad", 1),
                    "precio_unit": i.get("precio_unit", 0),
                }
                for i in items
            ],
        )
        self.refrescar()
        self.status_msg.emit(
            f"Cotización duplicada como COT-{nuevo_id} (estado: Pendiente)."
        )

    def _cambiar_estado(self):
        cot_id = self._fila_seleccionada()
        if cot_id is None:
            return
        dlg = _CambiarEstadoDialog(cot_id, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            self.refrescar()

    def _convertir_a_accion(self):
        cot_id = self._fila_seleccionada()
        if cot_id is None:
            return
        cot = self._cotizacion_por_id(cot_id)
        if not cot:
            return
        estado = cot.get("estado", "pendiente")
        if estado not in ("aceptada", "enviada"):
            QMessageBox.warning(
                self, "Estado no válido",
                "Solo puedes convertir cotizaciones en estado\n"
                "«Enviada» o «Aceptada» a acción de cobro.",
            )
            return
        total = float(cot.get("total") or 0)
        db.crear_accion(
            cliente          = cot.get("cliente", ""),
            factura_no       = f"COT-{cot_id}",
            tipo             = "seguimiento_cotizacion",
            prioridad        = 3,
            mensaje_sugerido = (
                f"Cotización N° {cot_id} por ${total:,.2f} — "
                "Dar seguimiento al cobro / confirmar facturación."
            ),
            fecha_sugerida   = datetime.now().strftime("%Y-%m-%d"),
        )
        QMessageBox.information(
            self, "Acción creada",
            "Se creó una acción de seguimiento en el tab 🎯 Acciones.\n"
            f"Cliente: {cot.get('cliente', '')}  —  Total: ${total:,.2f}",
        )
        self.status_msg.emit(f"Acción de seguimiento creada para {cot.get('cliente', '')}.")

    def _eliminar_seleccionada(self):
        cot_id = self._fila_seleccionada()
        if cot_id is None:
            return
        cot     = self._cotizacion_por_id(cot_id)
        cliente = cot.get("cliente", "") if cot else ""
        resp = QMessageBox.question(
            self, "Eliminar cotización",
            f"¿Eliminar la cotización COT-{cot_id} de {cliente}?\n"
            "Esta acción no se puede deshacer.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if resp == QMessageBox.Yes:
            db.eliminar_cotizacion(cot_id)
            self.refrescar()
            self.status_msg.emit("Cotización eliminada.")

    # ── Búsqueda global (Ctrl+F desde main_window) ───────────────────────────

    def buscar(self, texto: str) -> bool:
        self._search.setText(texto)
        if not texto:
            return False
        for r in range(self._tabla.rowCount()):
            if not self._tabla.isRowHidden(r):
                return True
        return False


# ─── Diálogo de envío ─────────────────────────────────────────────────────────

class _EnviarCotizacionDialog(QDialog):
    """Vista previa y envío de la cotización por email o WhatsApp."""

    def __init__(self, cotizacion: dict, items: list[dict], parent=None):
        super().__init__(parent)
        self._cotizacion = cotizacion
        self._items      = items
        self._canal      = "email"
        self._mensaje    = ""
        self.setWindowTitle("Enviar Cotización")
        self.setMinimumWidth(600)
        self.setMinimumHeight(460)
        self._build_ui()
        self._actualizar_preview()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        root.addWidget(_lbl("Elige cómo enviar:", bold=True))

        canal_row = QHBoxLayout()
        canal_row.setSpacing(8)

        self._btn_email = QPushButton("✉  Email")
        self._btn_email.setStyleSheet(_btn(_PINE))
        self._btn_email.clicked.connect(lambda: self._set_canal("email"))
        canal_row.addWidget(self._btn_email)

        self._btn_wa = QPushButton("💬  WhatsApp")
        self._btn_wa.setStyleSheet(_btn(_MUTED))
        self._btn_wa.clicked.connect(lambda: self._set_canal("whatsapp"))
        canal_row.addWidget(self._btn_wa)

        canal_row.addStretch()

        self._lbl_dest = QLabel()
        self._lbl_dest.setStyleSheet(
            f"color:{_MUTED}; font-size:11px; font-style:italic;"
        )
        canal_row.addWidget(self._lbl_dest)

        root.addLayout(canal_row)

        root.addWidget(_lbl("Vista previa — puedes editar antes de enviar:", bold=True))

        self._preview = QTextEdit()
        self._preview.setStyleSheet(
            f"QTextEdit {{ border:1px solid #d6cec5; border-radius:6px; "
            f"padding:8px; font-size:12px; background:{_SURF}; color:{_TEXT}; "
            f"font-family: 'Consolas', monospace; }}"
        )
        root.addWidget(self._preview)

        # Hint bajo la preview
        hint = QLabel(
            "✉ Email: se copiará el mensaje al portapapeles para pegarlo en tu cliente de correo.\n"
            "💬 WhatsApp: se abrirá WhatsApp Web con el mensaje prellenado."
        )
        hint.setStyleSheet(f"color:{_MUTED}; font-size:10px;")
        root.addWidget(hint)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{_MUTED}; font-size:12px; "
            f"border:1px solid #d6cec5; border-radius:6px; padding:5px 16px; }}"
            f"QPushButton:hover {{ color:{_TEXT}; border-color:{_TEXT}; }}"
        )
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        self._btn_enviar = QPushButton("Copiar mensaje")
        self._btn_enviar.setStyleSheet(_btn(_PINE))
        self._btn_enviar.clicked.connect(self._enviar)
        btn_row.addWidget(self._btn_enviar)

        root.addLayout(btn_row)

    def _set_canal(self, canal: str):
        self._canal = canal
        self._btn_email.setStyleSheet(_btn(_PINE if canal == "email" else _MUTED))
        self._btn_wa.setStyleSheet(_btn(_PINE if canal == "whatsapp" else _MUTED))
        self._actualizar_preview()
        self._btn_enviar.setText(
            "Copiar mensaje" if canal == "email" else "Abrir WhatsApp"
        )

    def _actualizar_preview(self):
        asunto, cuerpo = generar_mensaje_cotizacion(
            self._cotizacion, self._items, self._canal
        )
        self._mensaje = cuerpo
        txt = f"Asunto: {asunto}\n\n{cuerpo}" if self._canal == "email" and asunto else cuerpo
        self._preview.setPlainText(txt)

        email    = self._cotizacion.get("email", "")
        telefono = self._cotizacion.get("telefono", "")
        dest     = email if self._canal == "email" else telefono

        if dest:
            self._lbl_dest.setText(f"Para: {dest}")
        else:
            canal_label = "email" if self._canal == "email" else "teléfono"
            self._lbl_dest.setText(
                f"Sin {canal_label} — edita la cotización para agregar uno"
            )

    def _enviar(self):
        self._mensaje = self._preview.toPlainText()

        if self._canal == "whatsapp":
            telefono = self._cotizacion.get("telefono", "")
            if not telefono:
                QMessageBox.warning(
                    self, "Sin teléfono",
                    "Esta cotización no tiene teléfono registrado.\n"
                    "Edítala para agregarlo antes de enviar por WhatsApp.",
                )
                return
            url = generar_url_whatsapp(telefono, self._mensaje)
            webbrowser.open(url)
        else:
            from PyQt5.QtWidgets import QApplication
            QApplication.clipboard().setText(self._mensaje)
            self.status_bar_msg = (
                "Mensaje copiado. Pégalo en Gmail, Outlook u otro cliente de correo."
            )

        self.accept()

    def canal_usado(self) -> str:
        return self._canal

    def mensaje_usado(self) -> str:
        return self._mensaje


# ─── Diálogo de cambio de estado ─────────────────────────────────────────────

class _CambiarEstadoDialog(QDialog):

    _TRANSICIONES = {
        "pendiente": [
            ("📤 Marcar como Enviada",   "enviada",   _FOAM),
            ("❌ Marcar como Rechazada", "rechazada", _LOVE),
        ],
        "enviada": [
            ("✅ Marcar como Aceptada",  "aceptada",  _PINE),
            ("❌ Marcar como Rechazada", "rechazada", _LOVE),
            ("↩ Volver a Pendiente",     "pendiente", _GOLD),
        ],
        "aceptada": [
            ("↩ Volver a Enviada",       "enviada",   _FOAM),
            ("❌ Marcar como Rechazada", "rechazada", _LOVE),
        ],
        "rechazada": [
            ("↩ Reabrir como Pendiente", "pendiente", _GOLD),
        ],
    }

    def __init__(self, cotizacion_id: int, parent=None):
        super().__init__(parent)
        self._cot_id = cotizacion_id
        self.setWindowTitle("Cambiar estado de la cotización")
        self.setFixedWidth(340)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        cot    = db.get_cotizacion(self._cot_id)
        estado = cot.get("estado", "pendiente") if cot else "pendiente"
        label  = _ESTADO_LABEL.get(estado, estado)
        color  = _ESTADO_COLOR.get(estado, _MUTED)

        actual_lbl = QLabel(f"Estado actual:  {label}")
        actual_lbl.setStyleSheet(
            f"font-size:13px; font-weight:600; color:{color}; "
            f"padding: 6px 10px; background:{color}22; border-radius:6px;"
        )
        root.addWidget(actual_lbl)

        root.addWidget(_lbl("Cambiar a:", bold=True))

        transiciones = self._TRANSICIONES.get(estado, [])
        if not transiciones:
            root.addWidget(_lbl("No hay transiciones disponibles.", color=_MUTED))
        else:
            for texto, nuevo_estado, btn_color in transiciones:
                btn = QPushButton(texto)
                btn.setStyleSheet(_btn(btn_color))
                btn.clicked.connect(
                    lambda _, ns=nuevo_estado: self._aplicar(ns)
                )
                root.addWidget(btn)

        root.addSpacing(4)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{_MUTED}; font-size:12px; "
            f"border:1px solid #d6cec5; border-radius:6px; padding:5px 14px; }}"
            f"QPushButton:hover {{ color:{_TEXT}; border-color:{_TEXT}; }}"
        )
        btn_cancel.clicked.connect(self.reject)
        root.addWidget(btn_cancel)

    def _aplicar(self, nuevo_estado: str):
        db.actualizar_estado_cotizacion(self._cot_id, nuevo_estado)
        self.accept()
