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
    QFrame, QApplication, QGraphicsDropShadowEffect
)

try:
    import pyperclip
    PYPERCLIP_OK = True
except ImportError:
    PYPERCLIP_OK = False

from app import database as db
from app.config_manager import ConfigManager
from app.services.cobros_service import parse_reporte, totales
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
            f"border: 1px solid #e0d9d0;"
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
        _sep.setStyleSheet("color: #e0d9d0;")
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

        btn_xls = QPushButton("📂  Cargar XLS")
        btn_xls.setProperty("class", "primary")
        btn_xls.setToolTip("Cargar el reporte CarteraPorCobrar.xls de Contifico")
        btn_xls.clicked.connect(self._cargar_xls)
        row.addWidget(btn_xls)

        return row

    def _build_splitter(self) -> QSplitter:
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(2)

        # Panel izquierdo: lista
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        lbl = QLabel("Facturas")
        lbl.setStyleSheet(
            "color: #9893a5; font-size: 11px; font-weight: 600; "
            "text-transform: uppercase; letter-spacing: 0.8px;"
        )
        left_layout.addWidget(lbl)

        self.lista = QListWidget()
        self.lista.setAlternatingRowColors(False)
        self.lista.itemClicked.connect(self._on_item_click)
        left_layout.addWidget(self.lista, 1)

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
        sep.setStyleSheet("color: #e0d9d0;")

        btn_procesar = QPushButton("⚡  Procesar Todo")
        btn_procesar.setProperty("class", "primary")
        btn_procesar.setToolTip("Envía todos los emails pendientes en lote")
        btn_procesar.clicked.connect(self._procesar_todo)

        btn_plantillas = QPushButton("📝  Plantillas")
        btn_plantillas.setProperty("class", "secondary")
        btn_plantillas.setToolTip("Editar plantillas de mensajes")
        btn_plantillas.clicked.connect(self._abrir_plantillas)

        btn_rides = QPushButton("🔍  Escáner RIDES")
        btn_rides.setProperty("class", "secondary")
        btn_rides.setToolTip("Escanea la carpeta RIDES/ para actualizar contactos")
        btn_rides.clicked.connect(self._iniciar_escaner)

        btn_contifico = QPushButton("🔗  Contifico")
        btn_contifico.setProperty("class", "secondary")
        btn_contifico.setToolTip("Importar contactos de clientes desde la API de Contifico")
        btn_contifico.clicked.connect(self._abrir_contifico)

        row.addWidget(btn_plantillas)
        row.addWidget(btn_rides)
        row.addWidget(btn_contifico)
        row.addStretch()

        _sep_v = QFrame()
        _sep_v.setFrameShape(QFrame.VLine)
        _sep_v.setFixedWidth(1)
        _sep_v.setStyleSheet("color: #e0d9d0;")
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
            self, "Seleccionar reporte Contifico",
            str(Path.home()),
            "Archivos Excel (*.xls *.xlsx)"
        )
        if not ruta:
            return

        try:
            self._facturas_raw = parse_reporte(ruta)
        except Exception as e:
            QMessageBox.critical(self, "Error al cargar XLS", str(e))
            return

        if not self._facturas_raw:
            QMessageBox.information(
                self, "Sin datos",
                "El archivo no contiene facturas pendientes de cobro."
            )
            return

        self._actualizar_cards()
        self._aplicar_filtro(self._filtro_actual)
        self.status_msg.emit(
            f"{len(self._facturas_raw)} facturas cargadas desde {Path(ruta).name}"
        )

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

    def _aplicar_filtro(self, filtro: str):
        self._filtro_actual = filtro

        # Actualizar estado visual de botones
        for k, btn in self._btn_filtros.items():
            btn.setChecked(k == filtro)

        # Filtrar facturas
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

    # ── Selección de item ─────────────────────────────────────────────────

    def _on_item_click(self, item: FacturaItem):
        if not isinstance(item, FacturaItem):
            return

        f = item.factura
        contacto = item.contacto

        # Generar mensaje WhatsApp por defecto
        _, cuerpo = self._msg_service.generar(f, f["tipo"], "whatsapp")
        self.editor.setPlainText(cuerpo)

        # Habilitar botones según disponibilidad de contacto
        tiene_tel   = bool(contacto and contacto.get("telefono"))
        tiene_email = bool(contacto and contacto.get("email"))

        self.btn_copiar.setEnabled(True)
        self.btn_wa.setEnabled(tiene_tel)
        self.btn_email.setEnabled(tiene_email)

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

    # ── Contifico API ──────────────────────────────────────────────────────

    def _abrir_contifico(self):
        dlg = ContificoDialog(self)
        dlg.contactos_actualizados.connect(
            lambda: self._aplicar_filtro(self._filtro_actual)
        )
        dlg.exec_()
