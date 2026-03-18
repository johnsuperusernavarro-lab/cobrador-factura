"""
ui/cotizacion_form_dialog.py — Diálogo para crear o editar una cotización.

Cliente híbrido:
  - QCompleter con coincidencia parcial sobre la tabla contactos
  - Al seleccionar: auto-rellena email y teléfono
  - Si es nuevo: texto libre sin bloquear el flujo

Tabla de ítems:
  - Empty state con hint visible cuando no hay filas
  - Tab / Enter en la última celda → agrega nueva fila automáticamente
  - Columna Total calculada automáticamente (fondo diferenciado)
  - Auto-scroll y auto-focus al agregar fila
  - Presets rápidos de validez: 15 / 30 / 60 días
  - Fecha de vencimiento calculada en tiempo real
"""

import re
from datetime import date, timedelta

from PyQt5.QtCore import Qt, QStringListModel, QEvent
from PyQt5.QtGui import QColor, QBrush
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QSpinBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QCompleter, QFrame, QMessageBox, QAbstractItemView,
    QSizePolicy,
)

import core.database as db

_PINE  = "#286983"
_LOVE  = "#b4637a"
_GOLD  = "#ea9d34"
_FOAM  = "#56949f"
_TEXT  = "#575279"
_MUTED = "#9893a5"
_BG    = "#faf4ed"
_SURF  = "#fffaf3"
_OVR   = "#f2e9e1"
_CALC  = "#f0ede8"   # fondo columna calculada (Total)


def _lbl(texto: str, bold: bool = False, color: str = _TEXT) -> QLabel:
    lbl = QLabel(texto)
    style = f"color:{color}; font-size:12px;"
    if bold:
        style += " font-weight:600;"
    lbl.setStyleSheet(style)
    return lbl


def _input_style(focus_color: str = _PINE) -> str:
    return (
        f"QLineEdit {{ border:1px solid #d6cec5; border-radius:6px; "
        f"padding:5px 9px; font-size:12px; background:{_SURF}; color:{_TEXT}; }}"
        f"QLineEdit:focus {{ border-color:{focus_color}; }}"
    )


def _btn(color: str, text_color: str = "white") -> str:
    return (
        f"QPushButton {{ background:{color}; color:{text_color}; font-weight:600; "
        f"font-size:12px; border-radius:6px; padding:5px 14px; border:none; }}"
        f"QPushButton:hover {{ background:{color}dd; }}"
        f"QPushButton:disabled {{ background:#d6cec5; color:#a8a0a0; }}"
    )


def _btn_outline(color: str) -> str:
    return (
        f"QPushButton {{ background:transparent; color:{color}; font-size:11px; "
        f"font-weight:600; border:1px solid {color}; border-radius:6px; padding:3px 10px; }}"
        f"QPushButton:hover {{ background:{color}; color:white; }}"
    )


class CotizacionFormDialog(QDialog):
    """Diálogo modal para crear o editar una cotización."""

    def __init__(self, cotizacion_id: int | None = None, parent=None):
        super().__init__(parent)
        self._cotizacion_id   = cotizacion_id
        self._contacto_id: int | None = None
        self._contactos_cache: dict[str, dict] = {}
        self._tiene_cambios   = False

        titulo = "Editar Cotización" if cotizacion_id else "Nueva Cotización"
        self.setWindowTitle(titulo)
        self.setMinimumWidth(700)
        self.setMinimumHeight(580)

        self._build_ui()
        self._cargar_contactos()

        if cotizacion_id:
            self._cargar_datos_existentes(cotizacion_id)
        else:
            # Nueva cotización: agregar primera fila vacía para que el usuario empiece directo
            self._agregar_fila(auto_edit=True)

        # Después de cargar datos, instalar el tracker de cambios
        self._campo_cliente.textEdited.connect(self._marcar_cambio)
        self._campo_email.textEdited.connect(self._marcar_cambio)
        self._campo_telefono.textEdited.connect(self._marcar_cambio)
        self._campo_notas.textChanged.connect(self._marcar_cambio)
        self._tabla_items.itemChanged.connect(self._marcar_cambio)

    # ── Construcción ─────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(14)

        # ── Cliente ───────────────────────────────────────────────────────
        root.addWidget(_lbl("Cliente *", bold=True))

        cliente_row = QHBoxLayout()
        cliente_row.setSpacing(10)

        self._campo_cliente = QLineEdit()
        self._campo_cliente.setPlaceholderText(
            "Escribe el nombre — te sugerimos contactos existentes"
        )
        self._campo_cliente.setStyleSheet(_input_style())
        self._campo_cliente.textEdited.connect(self._on_cliente_editado)
        cliente_row.addWidget(self._campo_cliente, stretch=3)

        self._lbl_contacto = QLabel()
        self._lbl_contacto.setStyleSheet(
            f"color:{_MUTED}; font-size:11px; font-style:italic;"
        )
        self._lbl_contacto.setVisible(False)
        cliente_row.addWidget(self._lbl_contacto, stretch=2)

        root.addLayout(cliente_row)

        # ── Email y teléfono ──────────────────────────────────────────────
        contact_row = QHBoxLayout()
        contact_row.setSpacing(10)

        self._campo_email = QLineEdit()
        self._campo_email.setPlaceholderText("Email (para enviar por correo)")
        self._campo_email.setStyleSheet(_input_style())
        contact_row.addWidget(self._campo_email)

        self._campo_telefono = QLineEdit()
        self._campo_telefono.setPlaceholderText("Teléfono (para enviar por WhatsApp)")
        self._campo_telefono.setStyleSheet(_input_style())
        contact_row.addWidget(self._campo_telefono)

        root.addLayout(contact_row)

        # ── Separador ─────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color:#e0d9d0;")
        root.addWidget(sep)

        # ── Ítems ─────────────────────────────────────────────────────────
        items_hdr = QHBoxLayout()
        items_hdr.addWidget(_lbl("Ítems *", bold=True))
        items_hdr.addStretch()

        btn_add = QPushButton("＋ Agregar ítem")
        btn_add.setStyleSheet(_btn(_PINE))
        btn_add.setToolTip("Agrega una nueva fila  (también: Tab o Enter desde la última celda)")
        btn_add.clicked.connect(lambda: self._agregar_fila(auto_edit=True))
        items_hdr.addWidget(btn_add)

        self._btn_del_item = QPushButton("✕ Eliminar fila")
        self._btn_del_item.setStyleSheet(_btn(_LOVE))
        self._btn_del_item.setEnabled(False)
        self._btn_del_item.clicked.connect(self._eliminar_fila)
        items_hdr.addWidget(self._btn_del_item)

        root.addLayout(items_hdr)

        # Tabla de ítems
        self._tabla_items = QTableWidget(0, 4)
        self._tabla_items.setHorizontalHeaderLabels(
            ["Descripción", "Cantidad", "Precio Unitario", "Total  (auto)"]
        )
        hdr = self._tabla_items.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._tabla_items.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tabla_items.setAlternatingRowColors(True)
        self._tabla_items.setStyleSheet(
            f"QTableWidget {{ border:1px solid #d6cec5; border-radius:6px; "
            f"background:{_SURF}; font-size:12px; color:{_TEXT}; }}"
            f"QTableWidget::item {{ padding:5px; }}"
            f"QHeaderView::section {{ background:{_OVR}; color:{_TEXT}; "
            f"font-weight:600; padding:5px; border:none; }}"
        )
        self._tabla_items.setMinimumHeight(150)
        self._tabla_items.itemChanged.connect(self._recalcular_total)
        self._tabla_items.itemSelectionChanged.connect(self._on_items_seleccion)

        # Event filter: Tab/Enter en última celda → nueva fila;
        # viewport resize → reposicionar el hint overlay
        self._tabla_items.installEventFilter(self)
        self._tabla_items.viewport().installEventFilter(self)

        root.addWidget(self._tabla_items)

        # Hint overlay sobre la tabla (visible cuando no hay ítems)
        self._hint_overlay = QLabel(
            "Haz clic en '＋ Agregar ítem' para empezar\n"
            "o presiona Tab / Enter desde la última celda para agregar la siguiente fila",
            self._tabla_items.viewport(),
        )
        self._hint_overlay.setAlignment(Qt.AlignCenter)
        self._hint_overlay.setStyleSheet(
            f"color:{_MUTED}; font-size:12px; background:transparent;"
        )
        self._hint_overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._hint_overlay.hide()

        # ── Total general ─────────────────────────────────────────────────
        total_row = QHBoxLayout()
        total_row.addStretch()
        self._lbl_total = QLabel("TOTAL:  $0.00")
        self._lbl_total.setStyleSheet(
            f"font-size:16px; font-weight:700; color:{_PINE}; padding-right:4px;"
        )
        total_row.addWidget(self._lbl_total)
        root.addLayout(total_row)

        # ── Validez ───────────────────────────────────────────────────────
        validez_row = QHBoxLayout()
        validez_row.setSpacing(10)
        validez_row.addWidget(_lbl("Validez:"))

        # Presets rápidos
        for dias, etiqueta in [(15, "15 días"), (30, "30 días"), (60, "60 días")]:
            btn_p = QPushButton(etiqueta)
            btn_p.setStyleSheet(_btn_outline(_PINE))
            btn_p.setFixedWidth(72)
            btn_p.clicked.connect(lambda _, d=dias: self._set_validez(d))
            validez_row.addWidget(btn_p)

        validez_row.addSpacing(6)

        self._spin_validez = QSpinBox()
        self._spin_validez.setRange(1, 365)
        self._spin_validez.setValue(30)
        self._spin_validez.setSuffix(" días")
        self._spin_validez.setFixedWidth(100)
        self._spin_validez.setStyleSheet(
            f"QSpinBox {{ border:1px solid #d6cec5; border-radius:6px; "
            f"padding:4px 8px; font-size:12px; background:{_SURF}; color:{_TEXT}; }}"
        )
        self._spin_validez.valueChanged.connect(self._actualizar_fecha_fin)
        validez_row.addWidget(self._spin_validez)

        self._lbl_fecha_fin = QLabel()
        self._lbl_fecha_fin.setStyleSheet(f"color:{_MUTED}; font-size:11px;")
        validez_row.addWidget(self._lbl_fecha_fin)

        validez_row.addStretch()
        root.addLayout(validez_row)
        self._actualizar_fecha_fin(30)

        # ── Notas ─────────────────────────────────────────────────────────
        root.addWidget(_lbl("Notas / Observaciones:"))
        self._campo_notas = QTextEdit()
        self._campo_notas.setPlaceholderText(
            "Condiciones de pago, plazos de entrega, aclaraciones…"
        )
        self._campo_notas.setFixedHeight(68)
        self._campo_notas.setStyleSheet(
            f"QTextEdit {{ border:1px solid #d6cec5; border-radius:6px; "
            f"padding:6px; font-size:12px; background:{_SURF}; color:{_TEXT}; }}"
            f"QTextEdit:focus {{ border-color:{_PINE}; }}"
        )
        root.addWidget(self._campo_notas)

        # ── Botones ───────────────────────────────────────────────────────
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

        self._btn_guardar = QPushButton(
            "Guardar cambios" if self._cotizacion_id else "Crear cotización"
        )
        self._btn_guardar.setStyleSheet(_btn(_PINE))
        self._btn_guardar.clicked.connect(self._guardar)
        btn_row.addWidget(self._btn_guardar)

        root.addLayout(btn_row)

    # ── Event filter: Tab/Enter → nueva fila; viewport resize ────────────────

    def eventFilter(self, obj, event):
        if obj is self._tabla_items.viewport():
            if event.type() == QEvent.Resize:
                self._reposicionar_hint()
        elif obj is self._tabla_items:
            if event.type() == QEvent.KeyPress:
                key = event.key()
                if key in (Qt.Key_Tab, Qt.Key_Return, Qt.Key_Enter):
                    row = self._tabla_items.currentRow()
                    col = self._tabla_items.currentColumn()
                    # Tab/Enter en la última columna editable (col 2) de la última fila
                    if col == 2 and row == self._tabla_items.rowCount() - 1:
                        self._agregar_fila(auto_edit=True)
                        return True
        return super().eventFilter(obj, event)

    # ── Autocomplete de cliente ───────────────────────────────────────────────

    def _cargar_contactos(self):
        contactos = db.get_todos_contactos()
        self._contactos_cache = {c["nombre_contifico"]: c for c in contactos}

        model = QStringListModel(sorted(self._contactos_cache.keys()))
        self._completer = QCompleter(model, self)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchContains)
        self._completer.activated.connect(self._on_contacto_seleccionado)
        self._campo_cliente.setCompleter(self._completer)

    def _on_cliente_editado(self, texto: str):
        if texto not in self._contactos_cache:
            self._contacto_id = None
            self._lbl_contacto.setVisible(False)

    def _on_contacto_seleccionado(self, nombre: str):
        if nombre in self._contactos_cache:
            c = self._contactos_cache[nombre]
            self._contacto_id = c["id"]
            if c.get("email"):
                self._campo_email.setText(c["email"])
            if c.get("telefono"):
                self._campo_telefono.setText(c["telefono"])
            self._lbl_contacto.setText(f"✓ contacto vinculado")
            self._lbl_contacto.setStyleSheet(
                f"color:{_PINE}; font-size:11px; font-weight:600;"
            )
            self._lbl_contacto.setVisible(True)

    # ── Validez ───────────────────────────────────────────────────────────────

    def _set_validez(self, dias: int):
        self._spin_validez.setValue(dias)

    def _actualizar_fecha_fin(self, dias: int = None):
        if dias is None:
            dias = self._spin_validez.value()
        fecha_fin = date.today() + timedelta(days=dias)
        self._lbl_fecha_fin.setText(
            f"→ válida hasta el {fecha_fin.strftime('%d/%m/%Y')}"
        )

    # ── Tabla de ítems ────────────────────────────────────────────────────────

    def _on_items_seleccion(self):
        tiene = bool(self._tabla_items.selectedItems())
        self._btn_del_item.setEnabled(tiene)

    def _agregar_fila(self, desc: str = "", cant: float = 1.0,
                      precio: float = 0.0, auto_edit: bool = False):
        self._tabla_items.blockSignals(True)
        row = self._tabla_items.rowCount()
        self._tabla_items.insertRow(row)

        desc_item = QTableWidgetItem(str(desc))
        self._tabla_items.setItem(row, 0, desc_item)
        self._tabla_items.setItem(row, 1, QTableWidgetItem(f"{cant:g}"))
        self._tabla_items.setItem(row, 2, QTableWidgetItem(f"{precio:.2f}"))

        total_item = QTableWidgetItem(f"{cant * precio:.2f}")
        total_item.setFlags(total_item.flags() & ~Qt.ItemIsEditable)
        total_item.setBackground(QBrush(QColor(_CALC)))
        total_item.setForeground(QColor(_PINE))
        self._tabla_items.setItem(row, 3, total_item)

        self._tabla_items.blockSignals(False)
        self._actualizar_lbl_total()
        self._actualizar_hint_overlay()

        if auto_edit:
            self._tabla_items.scrollToItem(desc_item)
            self._tabla_items.setCurrentCell(row, 0)
            self._tabla_items.editItem(desc_item)

    def _eliminar_fila(self):
        rows = sorted(
            {idx.row() for idx in self._tabla_items.selectedIndexes()},
            reverse=True,
        )
        for r in rows:
            self._tabla_items.removeRow(r)
        self._actualizar_lbl_total()
        self._actualizar_hint_overlay()

    def _recalcular_total(self, item: QTableWidgetItem):
        row = item.row()
        col = item.column()
        if col not in (1, 2):
            return
        try:
            cant   = float(self._tabla_items.item(row, 1).text().replace(",", "."))
            precio = float(self._tabla_items.item(row, 2).text().replace(",", "."))
        except (ValueError, AttributeError):
            return
        self._tabla_items.blockSignals(True)
        total_item = self._tabla_items.item(row, 3)
        if total_item is None:
            total_item = QTableWidgetItem()
            total_item.setFlags(total_item.flags() & ~Qt.ItemIsEditable)
            total_item.setBackground(QBrush(QColor(_CALC)))
            total_item.setForeground(QColor(_PINE))
            self._tabla_items.setItem(row, 3, total_item)
        total_item.setText(f"{cant * precio:.2f}")
        self._tabla_items.blockSignals(False)
        self._actualizar_lbl_total()

    def _actualizar_lbl_total(self):
        total = 0.0
        for r in range(self._tabla_items.rowCount()):
            item = self._tabla_items.item(r, 3)
            if item:
                try:
                    total += float(item.text())
                except ValueError:
                    pass
        self._lbl_total.setText(f"TOTAL:  ${total:,.2f}")

    def _actualizar_hint_overlay(self):
        vacio = self._tabla_items.rowCount() == 0
        self._hint_overlay.setVisible(vacio)
        if vacio:
            self._reposicionar_hint()

    def _reposicionar_hint(self):
        vp = self._tabla_items.viewport()
        self._hint_overlay.setGeometry(0, 0, vp.width(), vp.height())

    # ── Carga de datos existentes ─────────────────────────────────────────────

    def _cargar_datos_existentes(self, cotizacion_id: int):
        cot = db.get_cotizacion(cotizacion_id)
        if not cot:
            return

        self._campo_cliente.setText(cot.get("cliente", ""))
        self._campo_email.setText(cot.get("email") or "")
        self._campo_telefono.setText(cot.get("telefono") or "")
        self._spin_validez.setValue(int(cot.get("validez_dias") or 30))
        self._campo_notas.setPlainText(cot.get("notas") or "")

        cid = cot.get("contacto_id")
        if cid:
            self._contacto_id = cid
            # Buscar nombre en caché
            nombre = next(
                (n for n, c in self._contactos_cache.items() if c.get("id") == cid),
                None,
            )
            self._lbl_contacto.setText(
                f"✓ {nombre}" if nombre else "✓ contacto vinculado"
            )
            self._lbl_contacto.setStyleSheet(
                f"color:{_PINE}; font-size:11px; font-weight:600;"
            )
            self._lbl_contacto.setVisible(True)

        for item in db.get_items_cotizacion(cotizacion_id):
            self._agregar_fila(
                item.get("descripcion", ""),
                float(item.get("cantidad", 1)),
                float(item.get("precio_unit", 0)),
                auto_edit=False,
            )

    # ── Cancelar con advertencia ──────────────────────────────────────────────

    def reject(self):
        if self._tiene_cambios and self._tabla_items.rowCount() > 0:
            resp = QMessageBox.question(
                self, "¿Descartar cambios?",
                "Tienes cambios sin guardar.\n¿Salir sin guardar?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if resp == QMessageBox.No:
                return
        super().reject()

    def _marcar_cambio(self, *_):
        self._tiene_cambios = True

    # ── Guardar ───────────────────────────────────────────────────────────────

    def _items_de_tabla(self) -> list[dict]:
        items = []
        for r in range(self._tabla_items.rowCount()):
            desc_item   = self._tabla_items.item(r, 0)
            cant_item   = self._tabla_items.item(r, 1)
            precio_item = self._tabla_items.item(r, 2)
            if not desc_item:
                continue
            desc = desc_item.text().strip()
            if not desc:
                continue
            try:
                cant   = float((cant_item.text() if cant_item else "1").replace(",", "."))
                precio = float((precio_item.text() if precio_item else "0").replace(",", "."))
            except ValueError:
                cant, precio = 1.0, 0.0
            if cant <= 0:
                cant = 1.0
            if precio < 0:
                precio = 0.0
            items.append({"descripcion": desc, "cantidad": cant, "precio_unit": precio})
        return items

    def _guardar(self):
        cliente = self._campo_cliente.text().strip()
        if not cliente:
            QMessageBox.warning(
                self, "Falta el cliente",
                "El nombre del cliente es obligatorio para crear la cotización.",
            )
            self._campo_cliente.setFocus()
            return

        items = self._items_de_tabla()
        if not items:
            QMessageBox.warning(
                self, "Sin ítems",
                "Agrega al menos un ítem con descripción antes de guardar.",
            )
            return

        # Validación básica de email
        email = self._campo_email.text().strip()
        if email and "@" not in email:
            QMessageBox.warning(
                self, "Email no válido",
                f"«{email}» no parece un email válido.\n"
                "Corrígelo o déjalo en blanco.",
            )
            self._campo_email.setFocus()
            return

        # Advertencia si no hay forma de contacto
        telefono = self._campo_telefono.text().strip()
        if not email and not telefono:
            resp = QMessageBox.question(
                self, "Sin datos de contacto",
                "No tienes email ni teléfono.\n"
                "No podrás enviar esta cotización directamente.\n\n"
                "¿Guardar de todas formas?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if resp == QMessageBox.No:
                return

        validez = self._spin_validez.value()
        notas   = self._campo_notas.toPlainText().strip()

        if self._cotizacion_id:
            db.actualizar_cotizacion(
                self._cotizacion_id, cliente, self._contacto_id,
                email, telefono, validez, notas, items,
            )
        else:
            self._cotizacion_id = db.crear_cotizacion(
                cliente, self._contacto_id, email, telefono,
                validez, notas, items,
            )

        self._tiene_cambios = False
        self.accept()

    def cotizacion_id(self) -> int | None:
        return self._cotizacion_id
