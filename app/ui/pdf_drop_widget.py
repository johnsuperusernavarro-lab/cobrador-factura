"""
pdf_drop_widget.py — Módulo de envío rápido por arrastre de PDFs

Layout:
  [Zona de arrastre: "Arrastra facturas PDF aquí"]
  ──────────────────────────────────────────────────
  [Lista PDFs procesados]  |  [Tipo: ▼] [Canal: ▼]
                           |  [Editor mensaje]
                           |  [Copiar] [WhatsApp] [Email]
  [Limpiar]
"""

import webbrowser
from pathlib import Path

from PyQt5.QtCore import Qt, pyqtSignal, QThread
from PyQt5.QtGui import QColor, QFont, QDragEnterEvent, QDropEvent
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QListWidget, QListWidgetItem,
    QSplitter, QFrame, QComboBox, QFileDialog, QLineEdit,
    QApplication, QProgressBar, QSizePolicy
)

try:
    import pyperclip
    PYPERCLIP_OK = True
except ImportError:
    PYPERCLIP_OK = False

from app import database as db
from app.config_manager import ConfigManager
from app.services.pdf_extractor import extraer_datos
from app.services.message_service import MessageService
from app.services.email_service import EmailService


# ── Worker para extracción en background ─────────────────────────────────

class _ExtractionWorker(QThread):
    resultado = pyqtSignal(dict)   # datos extraídos de un PDF
    error     = pyqtSignal(str, str)  # ruta, mensaje error

    def __init__(self, rutas: list[Path]):
        super().__init__()
        self.rutas = rutas

    def run(self):
        for ruta in self.rutas:
            try:
                datos = extraer_datos(ruta)
                self.resultado.emit(datos)
            except Exception as e:
                self.error.emit(str(ruta), str(e))


# ── Zona de arrastre ─────────────────────────────────────────────────────

class DropZone(QFrame):
    """Frame grande con borde punteado que acepta PDFs arrastrados."""

    pdfs_soltados = pyqtSignal(list)   # list[Path]

    _STYLE_NORMAL = """
        QFrame {
            border: 2px dashed #c8c0b8;
            border-radius: 12px;
            background: #fffaf3;
        }
    """
    _STYLE_HOVER = """
        QFrame {
            border: 2px dashed #286983;
            border-radius: 12px;
            background: #dde8ed;
        }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(110)
        self.setMaximumHeight(130)
        self.setStyleSheet(self._STYLE_NORMAL)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(6)

        self._icono = QLabel("📄")
        self._icono.setAlignment(Qt.AlignCenter)
        font_ico = QFont()
        font_ico.setPointSize(22)
        self._icono.setFont(font_ico)
        self._icono.setStyleSheet("border: none; background: transparent;")
        layout.addWidget(self._icono)

        self._lbl = QLabel("Arrastra facturas PDF aquí")
        self._lbl.setAlignment(Qt.AlignCenter)
        self._lbl.setStyleSheet(
            "color: #9893a5; font-size: 13px; border: none; background: transparent;"
        )
        layout.addWidget(self._lbl)

        self._lbl2 = QLabel("o haz clic para seleccionar")
        self._lbl2.setAlignment(Qt.AlignCenter)
        self._lbl2.setStyleSheet(
            "color: #c8c0b8; font-size: 11px; border: none; background: transparent;"
        )
        layout.addWidget(self._lbl2)

    def mousePressEvent(self, event):
        """Clic → abrir diálogo de selección de archivos."""
        rutas, _ = QFileDialog.getOpenFileNames(
            self, "Seleccionar facturas PDF",
            str(Path.home()),
            "Facturas PDF (*.pdf)"
        )
        if rutas:
            self.pdfs_soltados.emit([Path(r) for r in rutas])

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            pdfs = self._filtrar_pdfs(event.mimeData().urls())
            if pdfs:
                event.acceptProposedAction()
                self.setStyleSheet(self._STYLE_HOVER)
                self._lbl.setText(f"Suelta {len(pdfs)} PDF(s)")
                return
        event.ignore()

    def dragLeaveEvent(self, event):
        self._restaurar_estilo()

    def dropEvent(self, event: QDropEvent):
        pdfs = self._filtrar_pdfs(event.mimeData().urls())
        self._restaurar_estilo()
        if pdfs:
            self.pdfs_soltados.emit(pdfs)
            event.acceptProposedAction()

    def _filtrar_pdfs(self, urls) -> list[Path]:
        return [
            Path(u.toLocalFile()) for u in urls
            if u.toLocalFile().lower().endswith(".pdf")
            and Path(u.toLocalFile()).exists()
        ]

    def _restaurar_estilo(self):
        self.setStyleSheet(self._STYLE_NORMAL)
        self._lbl.setText("Arrastra facturas PDF aquí")


# ── Item de la lista ─────────────────────────────────────────────────────

class PdfItem(QListWidgetItem):
    """Item con datos del PDF ya extraídos."""

    _ICONO_EMAIL_TEL = "●"
    _ICONO_PARCIAL   = "◑"
    _ICONO_NADA      = "○"
    _ICONO_OK        = "✓"

    def __init__(self, datos: dict):
        super().__init__()
        self.datos      = datos
        self.gestionado = False

        tiene_email = bool(datos.get("emails"))
        tiene_tel   = bool(datos.get("telefono"))

        if tiene_email and tiene_tel:
            icono = self._ICONO_EMAIL_TEL
            self._color = "#56949f"
        elif tiene_email or tiene_tel:
            icono = self._ICONO_PARCIAL
            self._color = "#ea9d34"
        else:
            icono = self._ICONO_NADA
            self._color = "#d7827a"

        cliente = (datos.get("razon_social") or datos.get("archivo", ""))[:38]
        fn      = datos.get("factura_no", "—")
        total   = datos.get("total", "")
        monto_str = f"  ·  ${total}" if total else ""

        self.setText(f"{icono}  {cliente}\n     FAC {fn}{monto_str}")
        self.setForeground(QColor(self._color))

    def marcar_gestionado(self):
        self.gestionado = True
        texto = self.text()
        for viejo in (self._ICONO_EMAIL_TEL, self._ICONO_PARCIAL, self._ICONO_NADA):
            texto = texto.replace(viejo + "  ", self._ICONO_OK + "  ", 1)
        self.setText(texto)
        self.setForeground(QColor("#9893a5"))


# ── Widget principal ─────────────────────────────────────────────────────

class PdfDropWidget(QWidget):
    """Módulo de envío rápido por arrastre de PDFs."""

    status_msg = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._msg_service = MessageService()
        self._worker: _ExtractionWorker | None = None
        self._setup_ui()

    # ── UI ────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(16, 14, 16, 12)

        # Zona de arrastre
        self._drop_zone = DropZone()
        self._drop_zone.pdfs_soltados.connect(self._procesar_pdfs)
        root.addWidget(self._drop_zone)

        # Barra de progreso (oculta hasta que haya extracción)
        self._progress = QProgressBar()
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(4)
        self._progress.setVisible(False)
        self._progress.setStyleSheet(
            "QProgressBar { border: none; background: #f2e9e1; border-radius: 2px; }"
            "QProgressBar::chunk { background: #286983; border-radius: 2px; }"
        )
        root.addWidget(self._progress)

        # Splitter: lista | editor
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(2)

        # Panel izquierdo — lista
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(4)

        lbl_lista = QLabel("Facturas procesadas")
        lbl_lista.setStyleSheet(
            "color: #9893a5; font-size: 11px; font-weight: 600;"
        )
        ll.addWidget(lbl_lista)

        self._lista = QListWidget()
        self._lista.itemClicked.connect(self._on_item_click)
        ll.addWidget(self._lista, 1)

        splitter.addWidget(left)

        # Panel derecho — controles + editor
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(8)

        # Fila de tipo + canal
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(8)

        lbl_tipo = QLabel("Tipo:")
        lbl_tipo.setStyleSheet("color: #9893a5; font-size: 11px;")
        ctrl_row.addWidget(lbl_tipo)

        self._combo_tipo = QComboBox()
        self._combo_tipo.addItem("Por vencer",  "por_vencer")
        self._combo_tipo.addItem("Vencida",     "vencida")
        self._combo_tipo.currentIndexChanged.connect(self._regenerar_mensaje)
        ctrl_row.addWidget(self._combo_tipo)

        ctrl_row.addSpacing(12)

        lbl_canal = QLabel("Canal:")
        lbl_canal.setStyleSheet("color: #9893a5; font-size: 11px;")
        ctrl_row.addWidget(lbl_canal)

        self._combo_canal = QComboBox()
        self._combo_canal.addItem("WhatsApp",  "whatsapp")
        self._combo_canal.addItem("Email",     "email")
        self._combo_canal.currentIndexChanged.connect(self._regenerar_mensaje)
        ctrl_row.addWidget(self._combo_canal)

        ctrl_row.addStretch()
        rl.addLayout(ctrl_row)

        # Fila de contacto editable
        contact_row = QHBoxLayout()
        contact_row.setSpacing(6)

        lbl_ce = QLabel("Email:")
        lbl_ce.setStyleSheet("color: #9893a5; font-size: 11px;")
        lbl_ce.setFixedWidth(40)
        self._edit_dest_email = QLineEdit()
        self._edit_dest_email.setPlaceholderText("email@cliente.com  (editable)")
        self._edit_dest_email.textChanged.connect(self._on_contacto_changed)

        lbl_ct = QLabel("Tel:")
        lbl_ct.setStyleSheet("color: #9893a5; font-size: 11px;")
        lbl_ct.setFixedWidth(28)
        self._edit_dest_tel = QLineEdit()
        self._edit_dest_tel.setPlaceholderText("09XXXXXXXX  (editable)")
        self._edit_dest_tel.textChanged.connect(self._on_contacto_changed)

        contact_row.addWidget(lbl_ce)
        contact_row.addWidget(self._edit_dest_email, 3)
        contact_row.addSpacing(8)
        contact_row.addWidget(lbl_ct)
        contact_row.addWidget(self._edit_dest_tel, 2)
        rl.addLayout(contact_row)

        # Editor
        self._editor = QTextEdit()
        self._editor.setPlaceholderText(
            "Arrastra un PDF a la zona superior y selecciónalo aquí…"
        )
        self._editor.setAcceptRichText(False)
        rl.addWidget(self._editor, 1)

        # Botones de envío
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._btn_copiar = QPushButton("📋  Copiar")
        self._btn_copiar.setProperty("class", "secondary")
        self._btn_copiar.setToolTip("Copia el mensaje al portapapeles")
        self._btn_copiar.clicked.connect(self._copiar)
        self._btn_copiar.setEnabled(False)

        self._btn_wa = QPushButton("💬  WhatsApp")
        self._btn_wa.setProperty("class", "whatsapp")
        self._btn_wa.setToolTip("Abre WhatsApp Web con el mensaje prellenado")
        self._btn_wa.clicked.connect(self._abrir_whatsapp)
        self._btn_wa.setEnabled(False)

        self._btn_email = QPushButton("📧  Email")
        self._btn_email.setProperty("class", "primary")
        self._btn_email.setToolTip("Envía por email con el PDF adjunto")
        self._btn_email.clicked.connect(self._enviar_email)
        self._btn_email.setEnabled(False)

        btn_row.addStretch()
        btn_row.addWidget(self._btn_copiar)
        btn_row.addWidget(self._btn_wa)
        btn_row.addWidget(self._btn_email)
        rl.addLayout(btn_row)

        splitter.addWidget(right)
        splitter.setSizes([300, 500])
        root.addWidget(splitter, 1)

        # Barra inferior
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #e0d9d0;")
        root.addWidget(sep)

        bottom_row = QHBoxLayout()
        self._lbl_count = QLabel("Sin facturas cargadas")
        self._lbl_count.setStyleSheet("color: #9893a5; font-size: 11px;")
        bottom_row.addWidget(self._lbl_count)
        bottom_row.addStretch()

        btn_limpiar = QPushButton("Limpiar lista")
        btn_limpiar.setProperty("class", "secondary")
        btn_limpiar.clicked.connect(self._limpiar)
        bottom_row.addWidget(btn_limpiar)
        root.addLayout(bottom_row)

    # ── Procesamiento de PDFs ─────────────────────────────────────────────

    def _procesar_pdfs(self, rutas: list[Path]):
        if not rutas:
            return

        # Filtrar los que ya están en la lista (por nombre de archivo)
        existentes = set()
        for i in range(self._lista.count()):
            item = self._lista.item(i)
            if isinstance(item, PdfItem):
                existentes.add(item.datos.get("archivo", ""))

        nuevas = [r for r in rutas if r.name not in existentes]
        if not nuevas:
            self.status_msg.emit("Esos PDFs ya están en la lista")
            return

        # Barra de progreso
        self._progress.setRange(0, len(nuevas))
        self._progress.setValue(0)
        self._progress.setVisible(True)
        self._n_procesados = 0
        self._n_total_lote = len(nuevas)

        # Worker en background
        self._worker = _ExtractionWorker(nuevas)
        self._worker.resultado.connect(self._on_pdf_extraido)
        self._worker.error.connect(self._on_pdf_error)
        self._worker.finished.connect(self._on_extraccion_terminada)
        self._worker.start()

    def _on_pdf_extraido(self, datos: dict):
        item = PdfItem(datos)
        self._lista.addItem(item)

        self._n_procesados += 1
        self._progress.setValue(self._n_procesados)

        # Seleccionar automáticamente si es el primero
        if self._lista.count() == 1:
            self._lista.setCurrentRow(0)
            self._on_item_click(self._lista.item(0))

        self._actualizar_contador()

    def _on_pdf_error(self, ruta: str, msg: str):
        self._n_procesados += 1
        self._progress.setValue(self._n_procesados)
        self.status_msg.emit(f"Error leyendo {Path(ruta).name}: {msg}")

    def _on_extraccion_terminada(self):
        self._progress.setVisible(False)
        n = self._lista.count()
        self.status_msg.emit(f"{n} factura(s) lista(s) — selecciona una para editar el mensaje")

    # ── Selección de item ─────────────────────────────────────────────────

    def _on_item_click(self, item):
        if not isinstance(item, PdfItem):
            return
        self._regenerar_mensaje()

    def _regenerar_mensaje(self):
        item = self._lista.currentItem()
        if not isinstance(item, PdfItem):
            return

        datos  = item.datos
        tipo   = self._combo_tipo.currentData()
        canal  = self._combo_canal.currentData()

        # Adaptar dict al formato esperado por MessageService
        cliente_datos = {
            "cliente":     datos.get("razon_social", ""),
            "factura_no":  datos.get("factura_no", ""),
            "fecha":       datos.get("fecha", ""),
            "total":       datos.get("total", ""),
            "descripcion": datos.get("descripcion", ""),
        }

        _, cuerpo = self._msg_service.generar(cliente_datos, tipo, canal)
        self._editor.setPlainText(cuerpo)

        # Pre-llenar campos de contacto con datos del PDF (editables por el usuario)
        emails = datos.get("emails", [])
        self._edit_dest_email.setText(emails[0] if emails else "")
        self._edit_dest_tel.setText(datos.get("telefono", ""))

        # Habilitar botones según los campos (que el usuario puede haber modificado)
        self._btn_copiar.setEnabled(True)
        self._btn_wa.setEnabled(bool(self._edit_dest_tel.text().strip()))
        self._btn_email.setEnabled(bool(self._edit_dest_email.text().strip()))

    def _on_contacto_changed(self):
        """Actualiza estado de botones cuando el usuario edita email/teléfono."""
        item = self._lista.currentItem()
        if not isinstance(item, PdfItem):
            return
        self._btn_wa.setEnabled(bool(self._edit_dest_tel.text().strip()))
        self._btn_email.setEnabled(bool(self._edit_dest_email.text().strip()))

    # ── Acciones ──────────────────────────────────────────────────────────

    def _copiar(self):
        texto = self._editor.toPlainText()
        if not texto:
            return
        if PYPERCLIP_OK:
            pyperclip.copy(texto)
        else:
            QApplication.clipboard().setText(texto)

        item = self._lista.currentItem()
        if isinstance(item, PdfItem):
            d = item.datos
            db.registrar_envio(d.get("factura_no", ""), d.get("razon_social", ""),
                               "whatsapp", "ok")
            item.marcar_gestionado()

        self.status_msg.emit("Mensaje copiado al portapapeles ✓")

    def _abrir_whatsapp(self):
        item = self._lista.currentItem()
        if not isinstance(item, PdfItem):
            return

        tel = self._edit_dest_tel.text().strip()
        if not tel:
            return

        texto = self._editor.toPlainText()
        url   = self._msg_service.generar_url_whatsapp(tel, texto)
        webbrowser.open(url)

        d = item.datos
        db.registrar_envio(d.get("factura_no", ""), d.get("razon_social", ""),
                           "whatsapp", "ok")
        item.marcar_gestionado()
        self.status_msg.emit(f"WhatsApp abierto para {d.get('razon_social', '')} ✓")

    def _enviar_email(self):
        item = self._lista.currentItem()
        if not isinstance(item, PdfItem):
            return

        datos      = item.datos
        email_dest = self._edit_dest_email.text().strip()
        if not email_dest:
            return

        tipo  = self._combo_tipo.currentData()
        canal = "email"
        cliente_datos = {
            "cliente":     datos.get("razon_social", ""),
            "factura_no":  datos.get("factura_no", ""),
            "fecha":       datos.get("fecha", ""),
            "total":       datos.get("total", ""),
            "descripcion": datos.get("descripcion", ""),
        }
        asunto, cuerpo = self._msg_service.generar(cliente_datos, tipo, canal)

        ruta_pdf = Path(datos.get("ruta", ""))
        ok, err  = self._get_email_service().enviar(
            [email_dest], asunto, cuerpo,
            ruta_pdf if ruta_pdf.exists() else None
        )

        if ok:
            db.registrar_envio(datos.get("factura_no", ""),
                               datos.get("razon_social", ""), "email", "ok")
            item.marcar_gestionado()
            self.status_msg.emit(f"Email enviado a {email_dest} ✓")
        else:
            self.status_msg.emit(f"Error al enviar: {err}")

    def _get_email_service(self) -> EmailService:
        cfg = ConfigManager.get().get_email()
        return EmailService(cfg["address"], cfg["password"], cfg["provider"])

    # ── Utilidades ────────────────────────────────────────────────────────

    def _limpiar(self):
        self._lista.clear()
        self._editor.clear()
        self._edit_dest_email.clear()
        self._edit_dest_tel.clear()
        self._btn_copiar.setEnabled(False)
        self._btn_wa.setEnabled(False)
        self._btn_email.setEnabled(False)
        self._lbl_count.setText("Sin facturas cargadas")
        self.status_msg.emit("Lista limpiada")

    def _actualizar_contador(self):
        n = self._lista.count()
        self._lbl_count.setText(
            f"{n} factura{'s' if n != 1 else ''} cargada{'s' if n != 1 else ''}"
        )
