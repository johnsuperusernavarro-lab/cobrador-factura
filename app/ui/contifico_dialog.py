"""
contifico_dialog.py — Diálogo para conectar con la API de Contifico
y sincronizar contactos de clientes a la base de datos local.
"""

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QCheckBox,
    QProgressBar, QTextEdit, QFrame, QMessageBox,
)

from app.config_manager import ConfigManager
from app import database as db
from app.services.contifico_service import ContificoService, ContificoError


# ── Worker de verificación ────────────────────────────────────────────────────

class _VerifyWorker(QThread):
    resultado = pyqtSignal(bool, str)

    def __init__(self, token: str):
        super().__init__()
        self._token = token

    def run(self):
        svc = ContificoService(self._token)
        ok, msg = svc.verificar_conexion()
        self.resultado.emit(ok, msg)


# ── Worker de sincronización ──────────────────────────────────────────────────

class _SyncWorker(QThread):
    progreso  = pyqtSignal(int, int)          # actual, total
    log       = pyqtSignal(str)               # mensaje de texto
    terminado = pyqtSignal(int, int, int)     # nuevos, actualizados, sin_email
    error     = pyqtSignal(str)

    def __init__(self, token: str, solo_con_email: bool):
        super().__init__()
        self._token = token
        self._solo_con_email = solo_con_email
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        svc = ContificoService(self._token)
        try:
            self.log.emit("Conectando con Contifico…")
            clientes = svc.get_clientes(
                progreso_cb=lambda a, t: self.progreso.emit(a, t)
            )
        except ContificoError as e:
            self.error.emit(str(e))
            return

        total      = len(clientes)
        nuevos     = 0
        actualizados = 0
        sin_email  = 0

        self.log.emit(f"Se encontraron {total} clientes. Guardando contactos…")
        self.progreso.emit(0, total)

        for idx, c in enumerate(clientes, 1):
            if self._stop:
                break

            nombre = c["razon_social"]
            email  = c["email"]
            tel    = c["telefono"]

            if not nombre:
                continue
            if self._solo_con_email and not email:
                sin_email += 1
                self.progreso.emit(idx, total)
                continue

            # Verificar si ya existe para saber si es nuevo o actualización
            existente = db.get_contacto(nombre)
            db.upsert_contacto(
                nombre_contifico=nombre,
                email=email or None,
                telefono=tel or None,
                fuente="contifico_api",
                confianza=1.0,
            )
            if existente:
                actualizados += 1
            else:
                nuevos += 1

            self.progreso.emit(idx, total)

        self.terminado.emit(nuevos, actualizados, sin_email)


# ── Diálogo principal ─────────────────────────────────────────────────────────

class ContificoDialog(QDialog):
    """Diálogo para configurar y sincronizar contactos desde Contifico API."""

    contactos_actualizados = pyqtSignal()   # señal al widget padre para refrescar lista

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔗  Contifico — Sincronizar Contactos")
        self.setMinimumWidth(520)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._cfg     = ConfigManager.get()
        self._verify_worker: _VerifyWorker | None = None
        self._sync_worker:   _SyncWorker   | None = None

        self._setup_ui()
        self._cargar_token()

    # ── Construcción UI ───────────────────────────────────────────────────

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(20, 20, 20, 20)

        root.addWidget(self._build_token_group())
        root.addWidget(self._build_opciones_group())
        root.addWidget(self._build_progreso_group())
        root.addLayout(self._build_botones())

    def _build_token_group(self) -> QGroupBox:
        grp = QGroupBox("Credenciales de la API")
        lay = QVBoxLayout(grp)
        lay.setSpacing(10)

        # Descripción
        info = QLabel(
            "Ingresa el token de la API de Contifico para importar los datos\n"
            "de contacto (email y teléfono) de todos tus clientes."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #575279; font-size: 12px;")
        lay.addWidget(info)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        lay.addWidget(sep)

        # Campo token
        row_token = QHBoxLayout()
        lbl = QLabel("API Token:")
        lbl.setFixedWidth(90)
        self._edit_token = QLineEdit()
        self._edit_token.setEchoMode(QLineEdit.Password)
        self._edit_token.setPlaceholderText("Pega aquí tu token de Contifico")
        row_token.addWidget(lbl)
        row_token.addWidget(self._edit_token, 1)
        lay.addLayout(row_token)

        # Mostrar token
        chk = QCheckBox("Mostrar token")
        chk.toggled.connect(
            lambda on: self._edit_token.setEchoMode(
                QLineEdit.Normal if on else QLineEdit.Password
            )
        )
        lay.addWidget(chk)

        # Hint donde encontrar el token
        hint = QLabel(
            "ℹ  Encuéntralo en Contifico → Configuración → Integraciones → API"
        )
        hint.setStyleSheet("color: #9893a5; font-size: 11px;")
        lay.addWidget(hint)

        # Botón probar + resultado
        row_test = QHBoxLayout()
        row_test.addStretch()
        self._btn_probar = QPushButton("Probar conexión")
        self._btn_probar.setProperty("class", "secondary")
        self._btn_probar.clicked.connect(self._probar_conexion)
        row_test.addWidget(self._btn_probar)
        lay.addLayout(row_test)

        self._lbl_conn = QLabel("")
        self._lbl_conn.setAlignment(Qt.AlignCenter)
        self._lbl_conn.setMinimumHeight(18)
        lay.addWidget(self._lbl_conn)

        return grp

    def _build_opciones_group(self) -> QGroupBox:
        grp = QGroupBox("Opciones de sincronización")
        lay = QVBoxLayout(grp)

        self._chk_solo_email = QCheckBox(
            "Importar solo clientes que tienen correo electrónico registrado"
        )
        self._chk_solo_email.setChecked(True)
        lay.addWidget(self._chk_solo_email)

        nota = QLabel(
            "Los contactos existentes serán actualizados con los datos de Contifico.\n"
            "Los contactos ingresados manualmente no se eliminarán."
        )
        nota.setStyleSheet("color: #9893a5; font-size: 11px;")
        nota.setWordWrap(True)
        lay.addWidget(nota)

        return grp

    def _build_progreso_group(self) -> QGroupBox:
        grp = QGroupBox("Progreso")
        lay = QVBoxLayout(grp)
        lay.setSpacing(6)

        self._progress = QProgressBar()
        self._progress.setValue(0)
        self._progress.setTextVisible(True)
        lay.addWidget(self._progress)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(100)
        self._log.setStyleSheet("font-size: 11px; color: #575279;")
        self._log.setPlaceholderText("El registro de sincronización aparecerá aquí…")
        lay.addWidget(self._log)

        return grp

    def _build_botones(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addStretch()

        self._btn_cerrar = QPushButton("Cerrar")
        self._btn_cerrar.setProperty("class", "secondary")
        self._btn_cerrar.clicked.connect(self._on_cerrar)
        row.addWidget(self._btn_cerrar)

        self._btn_sync = QPushButton("⬇  Sincronizar Contactos")
        self._btn_sync.setProperty("class", "primary")
        self._btn_sync.clicked.connect(self._iniciar_sync)
        row.addWidget(self._btn_sync)

        return row

    # ── Lógica ────────────────────────────────────────────────────────────

    def _cargar_token(self):
        token = self._cfg.get_contifico().get("api_token", "")
        self._edit_token.setText(token)

    def _guardar_token(self):
        token = self._edit_token.text().strip()
        self._cfg.set_contifico(token)
        self._cfg.save()

    def _probar_conexion(self):
        token = self._edit_token.text().strip()
        if not token:
            self._set_conn_label(False, "Ingresa el token primero")
            return

        self._btn_probar.setEnabled(False)
        self._btn_probar.setText("Verificando…")
        self._lbl_conn.setText("")

        self._verify_worker = _VerifyWorker(token)
        self._verify_worker.resultado.connect(self._on_verificacion)
        self._verify_worker.start()

    def _on_verificacion(self, ok: bool, msg: str):
        self._btn_probar.setEnabled(True)
        self._btn_probar.setText("Probar conexión")
        self._set_conn_label(ok, msg)

    def _set_conn_label(self, ok: bool, texto: str):
        if ok:
            self._lbl_conn.setText(f"✓  {texto}")
            self._lbl_conn.setStyleSheet("color: #40a169; font-weight: 600; font-size: 12px;")
        else:
            self._lbl_conn.setText(f"✗  {texto}")
            self._lbl_conn.setStyleSheet("color: #d7827a; font-size: 12px;")

    def _iniciar_sync(self):
        token = self._edit_token.text().strip()
        if not token:
            QMessageBox.warning(self, "Token requerido",
                                "Ingresa el API token de Contifico antes de sincronizar.")
            return

        self._guardar_token()
        self._log.clear()
        self._progress.setValue(0)
        self._btn_sync.setEnabled(False)
        self._btn_cerrar.setEnabled(False)
        self._btn_sync.setText("Sincronizando…")

        solo_email = self._chk_solo_email.isChecked()
        self._sync_worker = _SyncWorker(token, solo_email)
        self._sync_worker.progreso.connect(self._on_progreso)
        self._sync_worker.log.connect(self._on_log)
        self._sync_worker.terminado.connect(self._on_terminado)
        self._sync_worker.error.connect(self._on_error)
        self._sync_worker.start()

    def _on_progreso(self, actual: int, total: int):
        self._progress.setMaximum(total)
        self._progress.setValue(actual)
        if total:
            self._progress.setFormat(f"{actual}/{total}  ({int(actual/total*100)}%)")

    def _on_log(self, msg: str):
        self._log.append(msg)

    def _on_terminado(self, nuevos: int, actualizados: int, sin_email: int):
        self._btn_sync.setEnabled(True)
        self._btn_cerrar.setEnabled(True)
        self._btn_sync.setText("⬇  Sincronizar Contactos")
        self._progress.setValue(self._progress.maximum())

        resumen = (
            f"✓  Sincronización completada:\n"
            f"   • Contactos nuevos:        {nuevos}\n"
            f"   • Contactos actualizados:  {actualizados}\n"
        )
        if sin_email:
            resumen += f"   • Omitidos (sin email):    {sin_email}\n"

        self._log.append(resumen)
        self.contactos_actualizados.emit()

        QMessageBox.information(
            self, "Sincronización completada",
            f"Se importaron {nuevos + actualizados} contactos desde Contifico.\n\n"
            f"  Nuevos:       {nuevos}\n"
            f"  Actualizados: {actualizados}"
            + (f"\n  Sin email:    {sin_email}" if sin_email else "")
        )

    def _on_error(self, msg: str):
        self._btn_sync.setEnabled(True)
        self._btn_cerrar.setEnabled(True)
        self._btn_sync.setText("⬇  Sincronizar Contactos")
        self._log.append(f"✗  Error: {msg}")
        QMessageBox.critical(self, "Error de conexión", msg)

    def _on_cerrar(self):
        if self._sync_worker and self._sync_worker.isRunning():
            self._sync_worker.stop()
            self._sync_worker.wait(2000)
        self.reject()

    def closeEvent(self, event):
        if self._sync_worker and self._sync_worker.isRunning():
            self._sync_worker.stop()
            self._sync_worker.wait(2000)
        super().closeEvent(event)
