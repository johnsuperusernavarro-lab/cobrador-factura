"""
cobros_widget.py — Vista principal del Cobrador de Facturas

Layout:
  [Cards: Total Vencido | Por Vencer]
  [Filtros: Todos | Vencidas | Por Vencer | Sin Contacto]  [Cargar XLS]
  [Lista facturas] | [Editor mensaje]  [Copiar | WhatsApp | Email]
  [Procesar Todo]  [Plantillas]  [Escáner RIDES]
"""

import webbrowser
from pathlib import Path

from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QListWidget, QListWidgetItem,
    QSplitter, QFileDialog, QMessageBox, QProgressDialog,
    QFrame, QApplication, QGraphicsDropShadowEffect,
    QLineEdit, QMenu, QAction, QDialog,
)

try:
    import pyperclip
    PYPERCLIP_OK = True
except ImportError:
    PYPERCLIP_OK = False

from app import database as db
from app.config_manager import ConfigManager
from app.services.cobros_service import totales
from app.services.xls_normalizer import normalizar_cartera
from app.services.message_service import MessageService
from app.services.email_service import EmailService
from app.services.rides_scanner import RidesScanner, UMBRAL_AUTO
from app.ui.confirm_dialog import ConfirmDialog
from app.ui.plantillas_dialog import PlantillasDialog
from app.ui.contifico_dialog import ContificoDialog

# ── Íconos de conectividad ─────────────────────────────────────────────────
ICONO_COMPLETO    = "●"   # email + teléfono
ICONO_PARCIAL     = "◑"   # solo uno
ICONO_SIN_CONT    = "○"   # ninguno
ICONO_LAPIZ       = "✎"   # fuzzy match pendiente
ICONO_GESTIONADO  = "✓"   # ya procesado

COLOR_COMPLETO    = "#56949f"
COLOR_PARCIAL     = "#ea9d34"
COLOR_SIN_CONT    = "#d7827a"
COLOR_GESTIONADO  = "#9893a5"


def _shadow(widget, blur=15, color="#c8c0b8"):
    """Agrega sombra suave a un widget."""
    sombra = QGraphicsDropShadowEffect()
    sombra.setBlurRadius(blur)
    sombra.setXOffset(0)
    sombra.setYOffset(2)
    sombra.setColor(QColor(color))
    widget.setGraphicsEffect(sombra)


class CardWidget(QFrame):
    """Card con título, monto y color de acento."""

    def __init__(self, titulo: str, color: str, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            f"background: #fffaf3; border-radius: 12px; "
            f"border: 1px solid #d6cec5;"
        )
        self.setMinimumSize(130, 52)
        self.setMaximumHeight(64)
        _shadow(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(2)

        self.lbl_titulo = QLabel(titulo)
        self.lbl_titulo.setStyleSheet(
            "color: #9893a5; font-size: 11px; font-weight: 600; "
            "text-transform: uppercase; letter-spacing: 0.8px; "
            "background: transparent; border: none;"
        )
        layout.addWidget(self.lbl_titulo)

        self.lbl_monto = QLabel("$0.00")
        font = QFont()
        font.setPointSize(14)
        font.setWeight(QFont.Bold)
        self.lbl_monto.setFont(font)
        self.lbl_monto.setStyleSheet(
            f"color: {color}; background: transparent; border: none;"
        )
        layout.addWidget(self.lbl_monto)

    def set_monto(self, valor: float, n: int = 0):
        self.lbl_monto.setText(f"${valor:,.2f}")
        if n:
            self.lbl_titulo.setText(
                self.lbl_titulo.text().split("(")[0].strip()
                + f"  ({n})"
            )


class FacturaItem(QListWidgetItem):
    """Item de la lista con datos de factura adjuntos."""

    def __init__(self, factura: dict, contacto: dict | None, pendiente: bool = False):
        super().__init__()
        self.factura  = factura
        self.contacto = contacto
        self.pendiente = pendiente   # fuzzy match sin confirmar
        self.gestionado = False

        # Icono de conectividad
        tiene_email = bool(contacto and contacto.get("email"))
        tiene_tel   = bool(contacto and contacto.get("telefono"))

        if tiene_email and tiene_tel:
            icono = ICONO_COMPLETO
            self._color = COLOR_COMPLETO
        elif tiene_email or tiene_tel:
            icono = ICONO_PARCIAL
            self._color = COLOR_PARCIAL
        else:
            icono = ICONO_SIN_CONT
            self._color = COLOR_SIN_CONT

        if pendiente:
            icono = ICONO_LAPIZ
            self._color = COLOR_PARCIAL

        # Tipo de factura
        tipo = factura.get("tipo", "")
        badge = "🔴" if tipo == "vencida" else "🔵"

        cliente = factura.get("cliente", "")[:38]
        monto   = factura.get("monto_pendiente", 0.0)
        fn      = factura.get("factura_no", "")

        texto = f"{icono}  {badge} {cliente}\n     FAC {fn}  ·  ${monto:,.2f}"
        self.setText(texto)
        self.setForeground(QColor(self._color))

    def marcar_gestionado(self):
        self.gestionado = True
        texto = self.text()
        if not texto.startswith(ICONO_GESTIONADO):
            self.setText(f"{ICONO_GESTIONADO} {texto}")
        self.setForeground(QColor(COLOR_GESTIONADO))


class CobrosWidget(QWidget):
    """Widget principal del módulo de cobros."""

    status_msg = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._facturas_raw: list[dict] = []
        self._filtro_actual = "todos"
        self._busqueda = ""
        self._msg_service = MessageService()
        self._scanner: RidesScanner | None = None

        self._setup_ui()
        db.init_db()

    # ── Construcción de la UI ──────────────────────────────────────────────

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(6)
        root.setContentsMargins(14, 8, 14, 8)

        # Cards + filtros en una sola fila compacta
        top = QHBoxLayout()
        top.setSpacing(10)
        top.addLayout(self._build_cards())
        _sep = QFrame()
        _sep.setFrameShape(QFrame.VLine)
        _sep.setStyleSheet("color: #d6cec5;")
        top.addWidget(_sep)
        top.addLayout(self._build_filtros())
        root.addLayout(top)

        # Splitter: lista | editor
        root.addWidget(self._build_splitter(), 1)

        # Barra inferior de acciones
        root.addLayout(self._build_barra_acciones())

    def _build_cards(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)

        self.card_vencido    = CardWidget("Total Vencido",    "#d7827a")
        self.card_por_vencer = CardWidget("Por Vencer",       "#286983")

        row.addWidget(self.card_vencido)
        row.addWidget(self.card_por_vencer)
        return row

    def _build_filtros(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        self._btn_filtros = {}
        filtros = [
            ("todos",        "Todos"),
            ("vencida",      "Vencidas"),
            ("por_vencer",   "Por Vencer"),
            ("sin_contacto", "Sin Contacto"),
        ]
        for clave, etiqueta in filtros:
            btn = QPushButton(etiqueta)
            btn.setProperty("class", "filter-pill")
            btn.setProperty("filtro", clave)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, k=clave: self._aplicar_filtro(k))
            self._btn_filtros[clave] = btn
            row.addWidget(btn)

        self._btn_filtros["todos"].setChecked(True)

        row.addStretch()

        btn_xls = QPushButton("📂  Cargar reporte de cartera")
        btn_xls.setProperty("class", "primary")
        btn_xls.setToolTip("Abre XLS, XLSX o CSV exportado desde tu sistema contable (Contifico, Alegra, Monica, etc.)")
        btn_xls.clicked.connect(self._cargar_xls)
        row.addWidget(btn_xls)

        return row

    def _build_splitter(self) -> QSplitter:
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(6)   # visible y arrastrable

        # Panel izquierdo: lista
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        lbl = QLabel("Facturas")
        lbl.setStyleSheet(
            "color: #797593; font-size: 12px; font-weight: 600;"
        )
        left_layout.addWidget(lbl)

        # ── Búsqueda por nombre (C3) ───────────────────────────────────
        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("🔍  Buscar cliente o factura…")
        self._search_box.setClearButtonEnabled(True)
        self._search_box.setStyleSheet(
            "QLineEdit { border:1px solid #d6cec5; border-radius:6px; "
            "padding:5px 8px; font-size:12px; background:#fffaf3; }"
            "QLineEdit:focus { border-color:#286983; }"
        )
        self._search_box.textChanged.connect(self._on_busqueda_changed)
        left_layout.addWidget(self._search_box)

        # ── Leyenda de íconos (C2) ─────────────────────────────────────
        legend_row = QHBoxLayout()
        legend_row.setSpacing(10)
        _ley = [
            ("●", "#56949f", "Email + Teléfono"),
            ("◑", "#ea9d34", "Solo uno"),
            ("○", "#d7827a", "Sin contacto"),
            ("✎", "#ea9d34", "Pendiente confirmar"),
        ]
        for icono, color, tooltip in _ley:
            dot = QLabel(icono)
            dot.setStyleSheet(f"color:{color}; font-size:13px;")
            dot.setToolTip(tooltip)
            legend_row.addWidget(dot)
        legend_row.addStretch()
        left_layout.addLayout(legend_row)

        self.lista = QListWidget()
        self.lista.setAlternatingRowColors(False)
        self.lista.itemClicked.connect(self._on_item_click)
        # Menú contextual (M16)
        self.lista.setContextMenuPolicy(Qt.CustomContextMenu)
        self.lista.customContextMenuRequested.connect(self._menu_contextual)
        left_layout.addWidget(self.lista, 1)

        # Overlay de estado vacío sobre el viewport de la lista
        self._hint_lista = QLabel("", self.lista.viewport())
        self._hint_lista.setAlignment(Qt.AlignCenter)
        self._hint_lista.setWordWrap(True)
        self._hint_lista.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._hint_lista.setStyleSheet(
            "color:#9893a5; font-size:12px; background:transparent; padding:24px;"
        )
        self.lista.viewport().installEventFilter(self)
        # visible inicialmente (no hay datos cargados)
        self._hint_lista.setText(
            "Sin datos cargados\n\n"
            "Usa  📂 Cargar reporte de cartera\n"
            "para subir tu XLS, o\n"
            "🔗 Conectar Nexo  para sincronizar\n"
            "desde tu sistema contable."
        )

        splitter.addWidget(left)

        # Panel derecho: editor + botones de envío
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        lbl2 = QLabel("Mensaje")
        lbl2.setStyleSheet(
            "color: #9893a5; font-size: 11px; font-weight: 600; "
            "text-transform: uppercase; letter-spacing: 0.8px;"
        )
        right_layout.addWidget(lbl2)

        # ── Client header (oculto hasta que haya selección) ────────────────
        self._client_header = QFrame()
        self._client_header.setProperty("class", "client-header")
        self._client_header.setVisible(False)
        _ch_row = QHBoxLayout(self._client_header)
        _ch_row.setContentsMargins(12, 8, 12, 8)
        _ch_row.setSpacing(6)

        _ch_left = QVBoxLayout()
        _ch_left.setSpacing(2)
        self._lbl_ch_cliente = QLabel()
        self._lbl_ch_cliente.setStyleSheet(
            "font-weight: 600; font-size: 13px; color: #575279; "
            "background: transparent; border: none;"
        )
        self._lbl_ch_factura = QLabel()
        self._lbl_ch_factura.setStyleSheet(
            "font-size: 11px; color: #9893a5; background: transparent; border: none;"
        )
        _ch_left.addWidget(self._lbl_ch_cliente)
        _ch_left.addWidget(self._lbl_ch_factura)

        self._lbl_ch_monto = QLabel()
        self._lbl_ch_monto.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._lbl_ch_monto.setStyleSheet(
            "font-weight: 700; font-size: 16px; color: #575279; "
            "background: transparent; border: none;"
        )
        _ch_row.addLayout(_ch_left)
        _ch_row.addStretch()
        _ch_row.addWidget(self._lbl_ch_monto)

        right_layout.addWidget(self._client_header)
        # ───────────────────────────────────────────────────────────────────

        self.editor = QTextEdit()
        self.editor.setPlaceholderText(
            "Selecciona una factura de la lista para ver el mensaje generado..."
        )
        right_layout.addWidget(self.editor, 1)

        # Botones de envío
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.btn_copiar = QPushButton("📋  Copiar")
        self.btn_copiar.setProperty("class", "secondary")
        self.btn_copiar.setToolTip("Copia el mensaje al portapapeles")
        self.btn_copiar.clicked.connect(self._copiar)
        self.btn_copiar.setEnabled(False)

        self.btn_wa = QPushButton("💬  WhatsApp")
        self.btn_wa.setProperty("class", "whatsapp")
        self.btn_wa.setToolTip("Abre WhatsApp Web con el mensaje prellenado")
        self.btn_wa.clicked.connect(self._abrir_whatsapp)
        self.btn_wa.setEnabled(False)

        self.btn_email = QPushButton("📧  Email")
        self.btn_email.setProperty("class", "primary")
        self.btn_email.setToolTip("Envía el mensaje por email")
        self.btn_email.clicked.connect(self._enviar_email_individual)
        self.btn_email.setEnabled(False)

        btn_row.addStretch()
        btn_row.addWidget(self.btn_copiar)
        btn_row.addWidget(self.btn_wa)
        btn_row.addWidget(self.btn_email)
        right_layout.addLayout(btn_row)

        splitter.addWidget(right)
        splitter.setSizes([320, 480])

        return splitter

    def _build_barra_acciones(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #d6cec5;")

        btn_procesar = QPushButton("📧  Envío masivo")
        btn_procesar.setProperty("class", "primary")
        btn_procesar.setToolTip("Envía emails a todos los clientes pendientes que tienen email registrado")
        btn_procesar.clicked.connect(self._procesar_todo)

        btn_plantillas = QPushButton("📝  Plantillas")
        btn_plantillas.setProperty("class", "secondary")
        btn_plantillas.setToolTip("Editar plantillas de mensajes")
        btn_plantillas.clicked.connect(self._abrir_plantillas)

        btn_rides = QPushButton("🔍  Escáner RIDES")
        btn_rides.setProperty("class", "secondary")
        btn_rides.setToolTip("Escanea la carpeta RIDES/ para actualizar contactos")
        btn_rides.clicked.connect(self._iniciar_escaner)

        btn_contifico = QPushButton("🔗  Conectar Nexo")
        btn_contifico.setProperty("class", "secondary")
        btn_contifico.setToolTip("Importar contactos de clientes desde tu sistema contable")
        btn_contifico.clicked.connect(self._abrir_contifico)

        btn_importar_ct = QPushButton("📥  Importar contactos")
        btn_importar_ct.setProperty("class", "secondary")
        btn_importar_ct.setToolTip("Importa email y teléfono desde cualquier Excel de agenda o directorio de clientes")
        btn_importar_ct.clicked.connect(self._importar_contactos_xls)

        btn_exportar = QPushButton("💾  Exportar")
        btn_exportar.setProperty("class", "secondary")
        btn_exportar.setToolTip("Exporta la lista filtrada actual a Excel o CSV")
        btn_exportar.clicked.connect(self._exportar_lista_actual)

        btn_historial = QPushButton("🕐  Historial")
        btn_historial.setProperty("class", "secondary")
        btn_historial.setToolTip("Ver y restaurar cargas anteriores")
        btn_historial.clicked.connect(self._abrir_historial)

        row.addWidget(btn_plantillas)
        row.addWidget(btn_rides)
        row.addWidget(btn_contifico)
        row.addWidget(btn_importar_ct)
        row.addWidget(btn_exportar)
        row.addWidget(btn_historial)
        row.addStretch()

        _sep_v = QFrame()
        _sep_v.setFrameShape(QFrame.VLine)
        _sep_v.setFixedWidth(1)
        _sep_v.setStyleSheet("color: #d6cec5;")
        row.addWidget(_sep_v)

        row.addWidget(btn_procesar)

        container = QVBoxLayout()
        container.setSpacing(4)
        container.addWidget(sep)
        container.addLayout(row)

        # Lo envolvemos en un widget dummy para poder retornar layout
        wrapper = QHBoxLayout()
        wrapper.addLayout(container)
        return wrapper

    # ── Carga de XLS ──────────────────────────────────────────────────────

    def _cargar_xls(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Cargar cartera por cobrar",
            str(Path.home()),
            "Archivos de datos (*.xls *.xlsx *.csv)"
        )
        if not ruta:
            return

        try:
            resultado = normalizar_cartera(ruta)
        except Exception as e:
            QMessageBox.critical(self, "Error al cargar archivo", str(e))
            return

        if not resultado.facturas:
            QMessageBox.information(
                self, "Sin datos",
                "El archivo no contiene facturas pendientes de cobro."
            )
            return

        # ── Diálogo de validación visual ──────────────────────────────────
        # El usuario valida el mapeo, la vista previa y las advertencias
        # ANTES de que se guarde cualquier dato en la base de datos.
        from app.ui.debug_normalizer_dialog import DebugNormalizerDialog
        dlg = DebugNormalizerDialog(resultado, Path(ruta).name, parent=self)
        if dlg.exec_() != QDialog.Accepted:
            return   # usuario canceló → no se persiste nada

        # A partir de aquí el usuario confirmó la carga
        self._facturas_raw = resultado.facturas

        # Guardar snapshot en historial
        monto_total = sum(f.get("monto_pendiente", 0) for f in resultado.facturas)
        try:
            from app import database as _db
            _db.registrar_carga_historial(
                software=resultado.software,
                n_facturas=len(resultado.facturas),
                monto_total=monto_total,
                nombre_archivo=Path(ruta).name,
                facturas=resultado.facturas,
            )
            _db.limpiar_historial_antiguo(mantener=5)
        except Exception:
            pass  # El historial es opcional; no interrumpir el flujo principal

        # Actualizar cache para el scheduler
        db.guardar_facturas_cache(resultado.facturas)

        # Mensaje de estado
        n_adv = len(resultado.advertencias)
        if n_adv:
            self.status_msg.emit(
                f"{len(self._facturas_raw)} facturas cargadas  ·  {n_adv} filas omitidas"
                f"  [{resultado.software}]"
            )
        else:
            self.status_msg.emit(
                f"{len(self._facturas_raw)} facturas cargadas "
                f"desde {Path(ruta).name}  [{resultado.software}]"
            )

        self._actualizar_cards()
        self._aplicar_filtro(self._filtro_actual)

    def _actualizar_cards(self):
        tot = totales(self._facturas_raw)
        self.card_vencido.set_monto(tot["total_vencido"],    tot["n_vencidas"])
        self.card_por_vencer.set_monto(tot["total_por_vencer"], tot["n_por_vencer"])
        self._actualizar_conteos_filtros()

    def _actualizar_conteos_filtros(self):
        """Actualiza los conteos dinámicos en los botones de filtro."""
        n_vencidas   = sum(1 for f in self._facturas_raw if f["tipo"] == "vencida")
        n_por_vencer = sum(1 for f in self._facturas_raw if f["tipo"] == "por_vencer")
        n_sin_cont   = sum(
            1 for f in self._facturas_raw
            if not self._tiene_contacto(f["cliente"])
        )
        self._btn_filtros["vencida"].setText(f"Vencidas ({n_vencidas})")
        self._btn_filtros["por_vencer"].setText(f"Por Vencer ({n_por_vencer})")
        self._btn_filtros["sin_contacto"].setText(f"Sin Contacto ({n_sin_cont})")

    # ── Filtros ───────────────────────────────────────────────────────────

    def _on_busqueda_changed(self, texto: str):
        self._busqueda = texto.lower().strip()
        self._aplicar_filtro(self._filtro_actual)

    def _aplicar_filtro(self, filtro: str):
        self._filtro_actual = filtro

        # Actualizar estado visual de botones
        for k, btn in self._btn_filtros.items():
            btn.setChecked(k == filtro)

        # Filtrar por tipo
        if filtro == "todos":
            facturas = self._facturas_raw
        elif filtro in ("vencida", "por_vencer"):
            facturas = [f for f in self._facturas_raw if f["tipo"] == filtro]
        elif filtro == "sin_contacto":
            facturas = [
                f for f in self._facturas_raw
                if not self._tiene_contacto(f["cliente"])
            ]
        else:
            facturas = self._facturas_raw

        # Filtrar por búsqueda de texto (C3)
        if self._busqueda:
            facturas = [
                f for f in facturas
                if self._busqueda in f.get("cliente", "").lower()
                or self._busqueda in f.get("factura_no", "").lower()
            ]

        self._poblar_lista(facturas)

    def _tiene_contacto(self, cliente: str) -> bool:
        c = db.get_contacto(cliente)
        return bool(c and (c.get("email") or c.get("telefono")))

    def _poblar_lista(self, facturas: list[dict]):
        self.lista.clear()
        self.editor.clear()
        self._deshabilitar_botones_envio()

        for f in facturas:
            contacto = db.get_contacto(f["cliente"])
            item = FacturaItem(f, contacto)
            self.lista.addItem(item)

        # Gestionar hint de estado vacío
        if not self._facturas_raw:
            self._hint_lista.setText(
                "Sin datos cargados\n\n"
                "Usa  📂 Cargar reporte de cartera\n"
                "para subir tu XLS, o\n"
                "🔗 Conectar Nexo  para sincronizar\n"
                "desde tu sistema contable."
            )
            self._hint_lista.show()
            self._reposicionar_hint_lista()
        elif not facturas:
            self._hint_lista.setText("Sin resultados para este filtro")
            self._hint_lista.show()
            self._reposicionar_hint_lista()
        else:
            self._hint_lista.hide()

    # ── Selección de item ─────────────────────────────────────────────────

    def _on_item_click(self, item: FacturaItem):
        if not isinstance(item, FacturaItem):
            return

        f = item.factura
        contacto = item.contacto

        # Generar mensaje WhatsApp por defecto
        _, cuerpo = self._msg_service.generar(f, f["tipo"], "whatsapp")
        self.editor.setPlainText(cuerpo)

        # Habilitar botones según disponibilidad de contacto (M4 — tooltips dinámicos)
        tiene_tel   = bool(contacto and contacto.get("telefono"))
        tiene_email = bool(contacto and contacto.get("email"))

        self.btn_copiar.setEnabled(True)
        self.btn_wa.setEnabled(tiene_tel)
        self.btn_email.setEnabled(tiene_email)

        self.btn_wa.setToolTip(
            "Abre WhatsApp Web con el mensaje prellenado" if tiene_tel
            else "Sin teléfono — agrégalo desde 🔗 Conectar Nexo o escaneando RIDES"
        )
        self.btn_email.setToolTip(
            "Envía el mensaje por email" if tiene_email
            else "Sin email — agrégalo desde 🔗 Conectar Nexo o escaneando RIDES"
        )

        # Actualizar header de cliente
        self._client_header.setVisible(True)
        self._lbl_ch_cliente.setText(f.get("cliente", ""))
        self._lbl_ch_factura.setText(f"FAC {f.get('factura_no', '')}")
        _monto = f.get("monto_pendiente", 0.0)
        _color_monto = "#d7827a" if f.get("tipo") == "vencida" else "#286983"
        self._lbl_ch_monto.setText(f"${_monto:,.2f}")
        self._lbl_ch_monto.setStyleSheet(
            f"font-weight: 700; font-size: 16px; color: {_color_monto}; "
            "background: transparent; border: none;"
        )

    def _menu_contextual(self, pos):
        """Menú clic derecho sobre la lista de facturas (M16)."""
        item = self.lista.itemAt(pos)
        if not isinstance(item, FacturaItem):
            return

        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#fffaf3; border:1px solid #d6cec5; border-radius:8px; padding:4px; }"
            "QMenu::item { padding:6px 20px; color:#575279; font-size:12px; border-radius:4px; }"
            "QMenu::item:selected { background:#dde8ed; color:#286983; }"
        )

        act_copiar = menu.addAction("📋  Copiar mensaje")
        act_copiar.triggered.connect(self._copiar)

        act_wa = menu.addAction("💬  Abrir WhatsApp")
        contacto = item.contacto
        tiene_tel = bool(contacto and contacto.get("telefono"))
        act_wa.setEnabled(tiene_tel)
        if not tiene_tel:
            act_wa.setToolTip("Sin teléfono registrado")
        act_wa.triggered.connect(self._abrir_whatsapp)

        act_email = menu.addAction("📧  Enviar email")
        tiene_email = bool(contacto and contacto.get("email"))
        act_email.setEnabled(tiene_email)
        act_email.triggered.connect(self._enviar_email_individual)

        menu.addSeparator()
        act_ok = menu.addAction("✓  Marcar como gestionado")
        def _marcar():
            item.marcar_gestionado()
        act_ok.triggered.connect(_marcar)

        menu.exec_(self.lista.viewport().mapToGlobal(pos))

    def _deshabilitar_botones_envio(self):
        self.btn_copiar.setEnabled(False)
        self.btn_wa.setEnabled(False)
        self.btn_email.setEnabled(False)
        self._client_header.setVisible(False)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _get_email_service(self) -> EmailService:
        cfg = ConfigManager.get().get_email()
        return EmailService(cfg["address"], cfg["password"], cfg["provider"])

    # ── Acciones de envío individuales ────────────────────────────────────

    def _copiar(self):
        texto = self.editor.toPlainText()
        if not texto:
            return
        if PYPERCLIP_OK:
            pyperclip.copy(texto)
        else:
            QApplication.clipboard().setText(texto)

        item = self.lista.currentItem()
        if isinstance(item, FacturaItem):
            f = item.factura
            db.registrar_envio(
                f.get("factura_no", ""), f.get("cliente", ""),
                "whatsapp", "ok"
            )
            item.marcar_gestionado()

        self.status_msg.emit("Mensaje copiado al portapapeles ✓")

    def _abrir_whatsapp(self):
        item = self.lista.currentItem()
        if not isinstance(item, FacturaItem):
            return
        contacto = item.contacto
        if not contacto or not contacto.get("telefono"):
            QMessageBox.warning(self, "Sin teléfono",
                                "Este cliente no tiene teléfono registrado.")
            return

        texto = self.editor.toPlainText()
        url = self._msg_service.generar_url_whatsapp(contacto["telefono"], texto)
        webbrowser.open(url)

        f = item.factura
        db.registrar_envio(f.get("factura_no", ""), f.get("cliente", ""),
                           "whatsapp", "ok")
        item.marcar_gestionado()
        self.status_msg.emit(f"WhatsApp abierto para {f.get('cliente', '')} ✓")

    def _enviar_email_individual(self):
        item = self.lista.currentItem()
        if not isinstance(item, FacturaItem):
            return
        contacto = item.contacto
        if not contacto or not contacto.get("email"):
            QMessageBox.warning(self, "Sin email",
                                "Este cliente no tiene email registrado.")
            return

        f = item.factura
        asunto, cuerpo = self._msg_service.generar(f, f["tipo"], "email")

        ok, err = self._get_email_service().enviar(
            [contacto["email"]], asunto, cuerpo
        )

        if ok:
            db.registrar_envio(f.get("factura_no", ""), f.get("cliente", ""),
                               "email", "ok")
            item.marcar_gestionado()
            self.status_msg.emit(f"Email enviado a {contacto['email']} ✓")
        else:
            QMessageBox.critical(self, "Error al enviar email", err)
            self.status_msg.emit(f"Error al enviar email: {err}")

    # ── Procesar Todo ─────────────────────────────────────────────────────

    def _procesar_todo(self):
        if not self._facturas_raw:
            QMessageBox.information(self, "Sin datos",
                                    "Carga primero un reporte XLS.")
            return

        enviados_hoy = {e["factura_no"] for e in db.get_enviados_hoy()}

        pendientes_email = []
        sin_contacto = 0

        for f in self._facturas_raw:
            fn = f.get("factura_no", "")
            if fn in enviados_hoy:
                continue
            c = db.get_contacto(f["cliente"])
            if c and c.get("email"):
                pendientes_email.append((f, c))
            else:
                sin_contacto += 1

        n_ya_enviados = sum(
            1 for f in self._facturas_raw
            if f.get("factura_no") in enviados_hoy
        )

        email_svc = self._get_email_service()
        if not email_svc.email:
            from PyQt5.QtWidgets import QMessageBox as _QMB
            _QMB.warning(
                self, "Sin configuración de correo",
                "Configura el correo en ⚙ Ajustes antes de enviar en lote."
            )
            return

        dlg = ConfirmDialog(
            n_emails=len(pendientes_email),
            n_sin_contacto=sin_contacto,
            n_ya_enviados=n_ya_enviados,
            parent=self
        )
        if dlg.exec_() != ConfirmDialog.Accepted:
            return

        # Envío en loop
        errores = []
        for idx, (f, contacto) in enumerate(pendientes_email, 1):
            dlg.mostrar_progreso(idx, len(pendientes_email), f.get("cliente", ""))
            QApplication.processEvents()

            asunto, cuerpo = self._msg_service.generar(f, f["tipo"], "email")
            ok, err = email_svc.enviar(
                [contacto["email"]], asunto, cuerpo
            )
            estado = "ok" if ok else "error"
            db.registrar_envio(f.get("factura_no", ""), f.get("cliente", ""),
                               "email", estado)
            if not ok:
                errores.append(f"{f.get('cliente', '')}: {err}")

        dlg.accept()

        if errores:
            QMessageBox.warning(
                self, "Envíos con error",
                f"Se completaron con {len(errores)} error(es):\n\n" +
                "\n".join(errores[:10])
            )
        else:
            self.status_msg.emit(
                f"Listo — {len(pendientes_email)} emails enviados ✓"
            )

        # Refrescar lista
        self._aplicar_filtro(self._filtro_actual)

    # ── Plantillas ────────────────────────────────────────────────────────

    def _abrir_plantillas(self):
        dlg = PlantillasDialog(self)
        dlg.exec_()

    # ── Escáner RIDES ─────────────────────────────────────────────────────

    def _iniciar_escaner(self):
        clientes = [f["cliente"] for f in self._facturas_raw]
        if not clientes:
            QMessageBox.information(
                self, "Sin datos",
                "Carga primero un reporte XLS para cruzar los nombres."
            )
            return

        # Diálogo de progreso
        self._progress_dlg = QProgressDialog(
            "Iniciando escáner RIDES…", "Cancelar", 0, 100, self
        )
        self._progress_dlg.setWindowTitle("Escáner RIDES")
        self._progress_dlg.setWindowModality(Qt.WindowModal)
        self._progress_dlg.setMinimumDuration(0)
        self._progress_dlg.setValue(0)
        self._progress_dlg.show()

        # QThread
        self._scanner = RidesScanner(clientes, parent=self)
        self._scanner.progreso.connect(self._on_scan_progreso)
        self._scanner.sugerencia.connect(self._on_scan_sugerencia)
        self._scanner.terminado.connect(self._on_scan_terminado)
        self._scanner.error.connect(self._on_scan_error)
        self._progress_dlg.canceled.connect(self._scanner.stop)
        self._scanner.start()

    def _on_scan_progreso(self, actual: int, total: int, nombre: str):
        if hasattr(self, "_progress_dlg"):
            pct = int(actual / total * 100) if total else 0
            self._progress_dlg.setMaximum(total)
            self._progress_dlg.setValue(actual)
            self._progress_dlg.setLabelText(
                f"Leyendo RIDES… ({actual}/{total})\n{nombre}"
            )

    def _on_scan_sugerencia(self, nombre_contifico: str, email: str,
                             telefono: str, confianza: float):
        fuente = "rides_scan"
        if confianza >= UMBRAL_AUTO:
            db.upsert_contacto(nombre_contifico, email or None,
                               telefono or None, fuente, confianza / 100)
        else:
            # Marcar como "pendiente de revisión" (confianza < umbral_auto)
            db.upsert_contacto(nombre_contifico, email or None,
                               telefono or None, "rides_revisar", confianza / 100)

    def _on_scan_terminado(self, n: int):
        if hasattr(self, "_progress_dlg"):
            self._progress_dlg.close()
        self.status_msg.emit(f"Escáner RIDES completado — {n} contacto(s) actualizados")
        # Refrescar lista para mostrar nuevos íconos de conectividad
        self._aplicar_filtro(self._filtro_actual)

    def _on_scan_error(self, mensaje: str):
        if hasattr(self, "_progress_dlg"):
            self._progress_dlg.close()
        QMessageBox.warning(self, "Error en escáner", mensaje)

    # ── Carga desde cache Contifico ───────────────────────────────────────

    def cargar_desde_cache(self):
        """Carga las facturas desde facturas_cache (sincronizadas desde Contifico)."""
        facturas = db.get_facturas_cache()
        if not facturas:
            return
        self._facturas_raw = facturas
        self._actualizar_cards()
        self._aplicar_filtro(self._filtro_actual)
        self.status_msg.emit(
            f"{len(facturas)} facturas cargadas desde Nexo ✓"
        )

    # ── Contifico API ──────────────────────────────────────────────────────

    def _abrir_contifico(self):
        dlg = ContificoDialog(self)
        dlg.contactos_actualizados.connect(
            lambda: self._aplicar_filtro(self._filtro_actual)
        )
        dlg.exec_()

    # ── Exportar ───────────────────────────────────────────────────────────

    def _get_facturas_visibles(self) -> list[dict]:
        """Retorna las facturas actualmente mostradas en la lista (tras filtros)."""
        facturas = []
        for i in range(self.lista.count()):
            item = self.lista.item(i)
            if isinstance(item, FacturaItem):
                facturas.append(item.factura)
        return facturas

    def _exportar_lista_actual(self):
        facturas = self._get_facturas_visibles()
        if not facturas:
            QMessageBox.information(self, "Sin datos", "No hay facturas para exportar.")
            return

        ruta, filtro = QFileDialog.getSaveFileName(
            self, "Exportar cartera",
            str(Path.home() / "cartera_export"),
            "Excel (*.xlsx);;CSV (*.csv)"
        )
        if not ruta:
            return

        from app.services.export_service import exportar_xlsx, exportar_csv
        if ruta.lower().endswith(".xlsx"):
            ok, err = exportar_xlsx(facturas, ruta)
        else:
            if not ruta.lower().endswith(".csv"):
                ruta += ".csv"
            ok, err = exportar_csv(facturas, ruta)

        if ok:
            self.status_msg.emit(
                f"Exportado: {Path(ruta).name}  ({len(facturas)} registros) ✓"
            )
        else:
            QMessageBox.critical(self, "Error al exportar", err)

    # ── Historial de cargas ────────────────────────────────────────────────

    def _abrir_historial(self):
        from app.ui.historial_dialog import HistorialDialog
        dlg = HistorialDialog(self)
        if dlg.exec_() == HistorialDialog.Accepted and dlg.facturas_restauradas:
            facturas = dlg.facturas_restauradas
            self._facturas_raw = facturas
            db.guardar_facturas_cache(facturas)
            self._actualizar_cards()
            self._aplicar_filtro(self._filtro_actual)
            self.status_msg.emit(
                f"Cartera restaurada desde historial — {len(facturas)} facturas ✓"
            )

    # ── Importar contactos desde XLS ──────────────────────────────────────

    def _importar_contactos_xls(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Importar contactos desde agenda / directorio de clientes",
            str(Path.home()),
            "Archivos de datos (*.xls *.xlsx *.csv)"
        )
        if not ruta:
            return

        from app.services.contactos_normalizer import normalizar_contactos, importar_contactos_a_db
        try:
            resultado = normalizar_contactos(ruta)
        except Exception as e:
            QMessageBox.critical(self, "Error al leer archivo", str(e))
            return

        if not resultado.contactos:
            QMessageBox.information(
                self, "Sin contactos",
                "No se encontraron contactos válidos (con email o teléfono) en el archivo."
            )
            return

        resp = QMessageBox.question(
            self, "Importar contactos",
            f"Se encontraron {len(resultado.contactos)} contactos en '{Path(ruta).name}'.\n"
            f"Software detectado: {resultado.software_detectado}\n\n"
            "¿Importar todos a la base de contactos?"
        )
        if resp != QMessageBox.Yes:
            return

        n_nuevos, n_actualizados = importar_contactos_a_db(resultado.contactos)
        self.status_msg.emit(
            f"Contactos importados: {n_nuevos} nuevos, {n_actualizados} actualizados ✓"
        )
        self._aplicar_filtro(self._filtro_actual)

    # ── Empty-state hint helpers ──────────────────────────────────────────

    def eventFilter(self, obj, event):
        from PyQt5.QtCore import QEvent
        if hasattr(self, "_hint_lista") and obj is self.lista.viewport():
            if event.type() == QEvent.Resize:
                self._reposicionar_hint_lista()
        return super().eventFilter(obj, event)

    def _reposicionar_hint_lista(self):
        if hasattr(self, "_hint_lista"):
            vp = self.lista.viewport()
            self._hint_lista.setGeometry(0, 0, vp.width(), vp.height())

    # ── Búsqueda global (contrato para main_window) ───────────────────────

    def buscar(self, texto: str) -> bool:
        """Aplica el texto de búsqueda y retorna True si hay resultados."""
        self._search_box.setText(texto)
        return self.lista.count() > 0
