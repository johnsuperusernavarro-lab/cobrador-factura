"""
settings_dialog.py — Diálogo de configuración: correo y WhatsApp
"""

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QLineEdit, QComboBox, QPushButton,
    QCheckBox, QFrame, QToolButton, QSizePolicy, QWidget,
    QScrollArea,
)

from app.config_manager import ConfigManager
from app.services.email_service import EmailService


# ── Worker para verificar credenciales en background ────────────────────────

class _VerifyWorker(QThread):
    resultado = pyqtSignal(bool, str)   # (ok, mensaje)

    def __init__(self, email: str, password: str, provider: str):
        super().__init__()
        self._email    = email
        self._password = password
        self._provider = provider

    def run(self):
        svc = EmailService(self._email, self._password, self._provider)
        ok, msg = svc.verificar_credenciales()
        self.resultado.emit(ok, msg)


# ── Panel colapsable reutilizable ────────────────────────────────────────────

class CollapsibleSection(QWidget):
    """Encabezado toggle + contenido show/hide para el diálogo de ajustes."""

    def __init__(self, title: str, content: QGroupBox,
                 expanded: bool = False, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Botón toggle
        self._btn = QToolButton()
        self._btn.setText(f"  {title}")
        self._btn.setCheckable(True)
        self._btn.setChecked(expanded)
        self._btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._btn.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self._btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._btn.setProperty("class", "section-toggle")
        self._btn.clicked.connect(self._toggle)

        # Contenido: quitar título del GroupBox (lo muestra el botón)
        # y unir visualmente el borde superior con el botón
        content.setTitle("")
        content.setStyleSheet(
            "QGroupBox { margin-top: 0; "
            "border-top-left-radius: 0; border-top-right-radius: 0; }"
        )
        self._content = content
        self._content.setVisible(expanded)

        layout.addWidget(self._btn)
        layout.addWidget(self._content)

    def _toggle(self, checked: bool):
        self._content.setVisible(checked)
        self._btn.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
        # Redimensionar el diálogo al contenido visible
        if self.window():
            self.window().adjustSize()


# ── Diálogo principal ────────────────────────────────────────────────────────

class SettingsDialog(QDialog):
    """Ventana de ajustes: correo electrónico y número de WhatsApp."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙  Ajustes — CONDORNEXUS")
        self.setMinimumWidth(480)
        self.setMinimumHeight(280)
        self.resize(490, 420)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._cfg    = ConfigManager.get()
        self._worker: _VerifyWorker | None = None

        self._setup_ui()
        self._cargar_valores()

    # ── Construcción de la UI ────────────────────────────────────────────

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # Contenedor con scroll por si la pantalla es pequeña
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setSpacing(6)
        inner_layout.setContentsMargins(20, 16, 20, 12)

        _secciones = [
            ("Correo Electrónico",            self._build_email_group(),     True),
            ("WhatsApp — Mi número",          self._build_whatsapp_group(),  False),
            ("Remitente (firma de mensajes)", self._build_remitente_group(), False),
            ("Datos Bancarios",               self._build_banco_group(),     False),
        ]
        for titulo, grp, abierto in _secciones:
            inner_layout.addWidget(CollapsibleSection(titulo, grp, expanded=abierto))

        inner_layout.addStretch()
        scroll.setWidget(inner)
        root.addWidget(scroll)

        # Botones fuera del scroll, siempre visibles
        btn_frame = QWidget()
        btn_frame.setStyleSheet(
            "QWidget { border-top: 1px solid #d6cec5; "
            "background-color: #faf4ed; }"
        )
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(20, 10, 20, 12)
        btn_layout.addLayout(self._build_botones())
        root.addWidget(btn_frame)

    # ── Grupo Email ───────────────────────────────────────────────────────

    def _build_email_group(self) -> QGroupBox:
        grp = QGroupBox("Correo Electrónico")
        lay = QVBoxLayout(grp)
        lay.setSpacing(10)

        # Proveedor
        row_prov = QHBoxLayout()
        lbl_prov = QLabel("Proveedor:")
        lbl_prov.setFixedWidth(95)
        self._combo_prov = QComboBox()
        self._combo_prov.addItem("Gmail",             "gmail")
        self._combo_prov.addItem("Hotmail / Outlook", "hotmail")
        self._combo_prov.addItem("Yahoo",             "yahoo")
        self._combo_prov.currentIndexChanged.connect(self._on_provider_changed)
        row_prov.addWidget(lbl_prov)
        row_prov.addWidget(self._combo_prov, 1)
        lay.addLayout(row_prov)

        # Dirección
        row_addr = QHBoxLayout()
        lbl_addr = QLabel("Correo:")
        lbl_addr.setFixedWidth(95)
        self._edit_email = QLineEdit()
        self._edit_email.setPlaceholderText("tu@gmail.com")
        row_addr.addWidget(lbl_addr)
        row_addr.addWidget(self._edit_email, 1)
        lay.addLayout(row_addr)

        # Contraseña
        row_pass = QHBoxLayout()
        lbl_pass = QLabel("Contraseña:")
        lbl_pass.setFixedWidth(95)
        self._edit_pass = QLineEdit()
        self._edit_pass.setEchoMode(QLineEdit.Password)
        self._edit_pass.setPlaceholderText("Contraseña de aplicación")
        row_pass.addWidget(lbl_pass)
        row_pass.addWidget(self._edit_pass, 1)
        lay.addLayout(row_pass)

        # Mostrar contraseña
        self._chk_ver = QCheckBox("Mostrar contraseña")
        self._chk_ver.toggled.connect(
            lambda on: self._edit_pass.setEchoMode(
                QLineEdit.Normal if on else QLineEdit.Password
            )
        )
        lay.addWidget(self._chk_ver)

        # Separador
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        lay.addWidget(sep)

        # Hint contextual
        self._lbl_hint = QLabel()
        self._lbl_hint.setWordWrap(True)
        self._lbl_hint.setStyleSheet("color: #9893a5; font-size: 11px;")
        lay.addWidget(self._lbl_hint)

        # Botón probar + resultado
        row_test = QHBoxLayout()
        row_test.addStretch()
        self._btn_probar = QPushButton("Probar conexión")
        self._btn_probar.setProperty("class", "secondary")
        self._btn_probar.clicked.connect(self._probar_conexion)
        row_test.addWidget(self._btn_probar)
        lay.addLayout(row_test)

        self._lbl_result = QLabel("")
        self._lbl_result.setAlignment(Qt.AlignCenter)
        self._lbl_result.setMinimumHeight(20)
        lay.addWidget(self._lbl_result)

        # Botón guardar individual
        row_save = QHBoxLayout()
        row_save.addStretch()
        self._lbl_email_saved = QLabel("")
        self._lbl_email_saved.setStyleSheet("color: #40a169; font-size: 11px;")
        row_save.addWidget(self._lbl_email_saved)
        btn_save = QPushButton("Guardar")
        btn_save.setStyleSheet(
            "QPushButton { background:#286983; color:#ffffff; font-weight:600; "
            "font-size:12px; border-radius:6px; padding:5px 16px; border:none; }"
            "QPushButton:hover { background:#1d4f63; }"
        )
        btn_save.clicked.connect(self._guardar_email)
        row_save.addWidget(btn_save)
        lay.addLayout(row_save)

        return grp

    # ── Grupo Remitente ───────────────────────────────────────────────────

    def _build_remitente_group(self) -> QGroupBox:
        grp = QGroupBox("Remitente (firma de mensajes)")
        lay = QVBoxLayout(grp)
        lay.setSpacing(10)

        campos = [
            ("Nombre:",   "nombre",  "Tu nombre completo"),
            ("Empresa:",  "empresa", "Nombre de tu empresa"),
            ("Cargo:",    "cargo",   "Tu cargo o rol"),
        ]
        self._rem_edits: dict = {}
        for lbl_txt, key, placeholder in campos:
            row = QHBoxLayout()
            lbl = QLabel(lbl_txt)
            lbl.setFixedWidth(80)
            edit = QLineEdit()
            edit.setPlaceholderText(placeholder)
            self._rem_edits[key] = edit
            row.addWidget(lbl)
            row.addWidget(edit, 1)
            lay.addLayout(row)

        row_save = QHBoxLayout()
        row_save.addStretch()
        self._lbl_rem_saved = QLabel("")
        self._lbl_rem_saved.setStyleSheet("color: #40a169; font-size: 11px;")
        row_save.addWidget(self._lbl_rem_saved)
        btn_save = QPushButton("Guardar")
        btn_save.setStyleSheet(
            "QPushButton { background:#286983; color:#ffffff; font-weight:600; "
            "font-size:12px; border-radius:6px; padding:5px 16px; border:none; }"
            "QPushButton:hover { background:#1d4f63; }"
        )
        btn_save.clicked.connect(self._guardar_remitente)
        row_save.addWidget(btn_save)
        lay.addLayout(row_save)

        return grp

    # ── Grupo Banco ───────────────────────────────────────────────────────

    def _build_banco_group(self) -> QGroupBox:
        grp = QGroupBox("Datos Bancarios (para mensajes de cobro)")
        lay = QVBoxLayout(grp)
        lay.setSpacing(10)

        campos = [
            ("Banco:",    "nombre",  "Ej: Banco Pichincha"),
            ("Titular:",  "titular", "Nombre del titular de la cuenta"),
            ("N° Cuenta:","numero",  "Número de cuenta"),
            ("Tipo:",     "tipo",    "Cta. Corriente / Cta. Ahorros"),
            ("C.I. / RUC:","ci",    "Cédula o RUC del titular"),
        ]
        self._ban_edits: dict = {}
        for lbl_txt, key, placeholder in campos:
            row = QHBoxLayout()
            lbl = QLabel(lbl_txt)
            lbl.setFixedWidth(80)
            edit = QLineEdit()
            edit.setPlaceholderText(placeholder)
            self._ban_edits[key] = edit
            row.addWidget(lbl)
            row.addWidget(edit, 1)
            lay.addLayout(row)

        row_save = QHBoxLayout()
        row_save.addStretch()
        self._lbl_ban_saved = QLabel("")
        self._lbl_ban_saved.setStyleSheet("color: #40a169; font-size: 11px;")
        row_save.addWidget(self._lbl_ban_saved)
        btn_save = QPushButton("Guardar")
        btn_save.setStyleSheet(
            "QPushButton { background:#286983; color:#ffffff; font-weight:600; "
            "font-size:12px; border-radius:6px; padding:5px 16px; border:none; }"
            "QPushButton:hover { background:#1d4f63; }"
        )
        btn_save.clicked.connect(self._guardar_banco)
        row_save.addWidget(btn_save)
        lay.addLayout(row_save)

        return grp

    # ── Grupo WhatsApp ────────────────────────────────────────────────────

    def _build_whatsapp_group(self) -> QGroupBox:
        grp = QGroupBox("WhatsApp — Mi número")
        lay = QVBoxLayout(grp)
        lay.setSpacing(10)

        row = QHBoxLayout()
        lbl = QLabel("Teléfono:")
        lbl.setFixedWidth(95)
        self._edit_tel = QLineEdit()
        self._edit_tel.setPlaceholderText("Ej: 0999999999")
        row.addWidget(lbl)
        row.addWidget(self._edit_tel, 1)
        lay.addLayout(row)

        hint = QLabel(
            "Número que aparece en la firma de los mensajes.\n"
            "Para actualizar el número dentro del texto de los mensajes,\n"
            "usa el botón 📝 Plantillas en la pantalla principal."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #9893a5; font-size: 11px;")
        lay.addWidget(hint)

        row_save = QHBoxLayout()
        row_save.addStretch()
        self._lbl_wa_saved = QLabel("")
        self._lbl_wa_saved.setStyleSheet("color: #40a169; font-size: 11px;")
        row_save.addWidget(self._lbl_wa_saved)
        btn_save = QPushButton("Guardar")
        btn_save.setStyleSheet(
            "QPushButton { background:#286983; color:#ffffff; font-weight:600; "
            "font-size:12px; border-radius:6px; padding:5px 16px; border:none; }"
            "QPushButton:hover { background:#1d4f63; }"
        )
        btn_save.clicked.connect(self._guardar_whatsapp)
        row_save.addWidget(btn_save)
        lay.addLayout(row_save)

        return grp

    # ── Botones ───────────────────────────────────────────────────────────

    def _build_botones(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch()

        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setProperty("class", "secondary")
        btn_cancel.clicked.connect(self.reject)
        row.addWidget(btn_cancel)

        btn_guardar = QPushButton("   Guardar   ")
        btn_guardar.setStyleSheet(
            "QPushButton { background:#286983; color:#ffffff; font-weight:600; "
            "font-size:12px; border-radius:6px; padding:5px 16px; border:none; }"
            "QPushButton:hover { background:#1d4f63; }"
        )
        btn_guardar.clicked.connect(self._guardar)
        row.addWidget(btn_guardar)

        return row

    # ── Lógica ────────────────────────────────────────────────────────────

    def _cargar_valores(self):
        cfg_email = self._cfg.get_email()
        cfg_wa    = self._cfg.get_whatsapp()
        cfg_rem   = self._cfg.get_remitente()
        cfg_ban   = self._cfg.get_banco()

        idx = self._combo_prov.findData(cfg_email.get("provider", "gmail"))
        if idx >= 0:
            self._combo_prov.setCurrentIndex(idx)

        self._edit_email.setText(cfg_email.get("address", ""))
        self._edit_pass.setText(cfg_email.get("password", ""))
        self._edit_tel.setText(cfg_wa.get("mi_telefono", ""))

        for key, edit in self._rem_edits.items():
            edit.setText(cfg_rem.get(key, ""))

        for key, edit in self._ban_edits.items():
            edit.setText(cfg_ban.get(key, ""))

        self._on_provider_changed()

    def _on_provider_changed(self, *_):
        provider = self._combo_prov.currentData()
        hints = {
            "gmail": (
                "Para Gmail necesitas activar la verificación en 2 pasos y luego\n"
                "generar una Contraseña de aplicación en:\n"
                "myaccount.google.com → Seguridad → Contraseñas de aplicación"
            ),
            "hotmail": (
                "Para Hotmail/Outlook activa la verificación en 2 pasos y genera\n"
                "una Contraseña de aplicación en:\n"
                "account.microsoft.com → Seguridad → Contraseñas de aplicación"
            ),
            "yahoo": (
                "Para Yahoo activa la verificación en 2 pasos y genera\n"
                "una Contraseña de aplicación en:\n"
                "account.yahoo.com → Seguridad → Generar contraseña de app"
            ),
        }
        self._lbl_hint.setText(hints.get(provider, ""))
        self._lbl_result.setText("")

    def _probar_conexion(self):
        email    = self._edit_email.text().strip()
        password = self._edit_pass.text()
        provider = self._combo_prov.currentData()

        if not email or not password:
            self._mostrar_resultado(False, "Completa el correo y la contraseña primero")
            return

        self._btn_probar.setEnabled(False)
        self._btn_probar.setText("Verificando…")
        self._lbl_result.setText("")

        self._worker = _VerifyWorker(email, password, provider)
        self._worker.resultado.connect(self._on_verificacion)
        self._worker.start()

    def _on_verificacion(self, ok: bool, msg: str):
        self._btn_probar.setEnabled(True)
        self._btn_probar.setText("Probar conexión")
        if ok:
            self._mostrar_resultado(True, "Conexión exitosa — credenciales correctas")
        else:
            short = msg.split("\n")[0][:90]
            self._mostrar_resultado(False, short)

    def _mostrar_resultado(self, ok: bool, texto: str):
        if ok:
            self._lbl_result.setText(f"✓  {texto}")
            self._lbl_result.setStyleSheet(
                "color: #40a169; font-weight: 600; font-size: 12px;"
            )
        else:
            self._lbl_result.setText(f"✗  {texto}")
            self._lbl_result.setStyleSheet("color: #d7827a; font-size: 12px;")

    def _guardar_email(self):
        self._cfg.set_email(
            provider=self._combo_prov.currentData(),
            address=self._edit_email.text().strip(),
            password=self._edit_pass.text(),
        )
        self._cfg.save()
        self._lbl_email_saved.setText("✓ Guardado")

    def _guardar_whatsapp(self):
        self._cfg.set_whatsapp(self._edit_tel.text().strip())
        self._cfg.save()
        self._lbl_wa_saved.setText("✓ Guardado")

    def _guardar_remitente(self):
        self._cfg.set_remitente(
            nombre=self._rem_edits["nombre"].text().strip(),
            empresa=self._rem_edits["empresa"].text().strip(),
            cargo=self._rem_edits["cargo"].text().strip(),
        )
        self._cfg.save()
        self._lbl_rem_saved.setText("✓ Guardado")

    def _guardar_banco(self):
        self._cfg.set_banco(
            nombre=self._ban_edits["nombre"].text().strip(),
            titular=self._ban_edits["titular"].text().strip(),
            numero=self._ban_edits["numero"].text().strip(),
            tipo=self._ban_edits["tipo"].text().strip() or "Cta. Corriente",
            ci=self._ban_edits["ci"].text().strip(),
        )
        self._cfg.save()
        self._lbl_ban_saved.setText("✓ Guardado")

    def _guardar(self):
        self._guardar_email()
        self._guardar_whatsapp()
        self._guardar_remitente()
        self._guardar_banco()
        self.accept()
