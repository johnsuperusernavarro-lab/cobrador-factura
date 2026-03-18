"""
ui/contifico_widget.py — Tab Contifico en la ventana principal desktop.

Muestra el estado de la conexión, métricas del cache y botones para
sincronizar facturas y contactos directamente desde Contifico.
"""

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QScrollArea,
    QProgressBar, QTextEdit, QGroupBox,
)

from app.config_manager import ConfigManager
from app import database as db
from app.services.contifico_service import ContificoService, ContificoError
from app.services.scoring_service import recalcular_todos_los_scores
from app.ui.contifico_dialog import ContificoDialog

# ── Paleta ───────────────────────────────────────────────────────────────────
_BG      = "#faf4ed"
_SURFACE = "#fffaf3"
_OVERLAY = "#f2e9e1"
_TEXT    = "#575279"
_MUTED   = "#9893a5"
_SUBTLE  = "#797593"
_PINE    = "#286983"
_LOVE    = "#b4637a"
_GOLD    = "#ea9d34"
_FOAM    = "#56949f"


class ContificoWidget(QWidget):
    """Tab Contifico: métricas, sync facturas, sync contactos."""

    status_msg            = pyqtSignal(str)
    facturas_sincronizadas = pyqtSignal()   # avisa a Cartera para refrescar

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.refrescar()

    # ── Construcción ─────────────────────────────────────────────────────────

    def _build_ui(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        inner = QWidget()
        inner.setMaximumWidth(1400)
        root = QVBoxLayout(inner)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(14)

        # ── Título de sección ─────────────────────────────────────────────
        hdr = QHBoxLayout()
        title = QLabel("Sincronizar Nexo")
        title.setStyleSheet(f"font-size:17px; font-weight:700; color:{_TEXT};")
        hdr.addWidget(title)
        hdr.addStretch()
        root.addLayout(hdr)

        # Estado conexión
        root.addLayout(self._build_conn_row())

        # Cards métricas
        root.addLayout(self._build_cards())

        # Sección importar facturas
        root.addWidget(self._build_facturas_section())

        # Botón para abrir diálogo completo (sync contactos + opciones)
        root.addWidget(self._build_contactos_section())

        root.addStretch()
        scroll.setWidget(inner)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _build_conn_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        lbl = QLabel("Estado de conexión:")
        lbl.setStyleSheet(f"color:{_SUBTLE}; font-size:13px;")
        row.addWidget(lbl)

        self._lbl_conn = QLabel("Verificando…")
        self._lbl_conn.setStyleSheet(
            f"color:{_MUTED}; font-size:12px; padding:3px 12px; "
            f"border-radius:12px; background:{_OVERLAY};"
        )
        row.addWidget(self._lbl_conn)

        # M11 — acceso directo a Ajustes cuando no hay token
        self._btn_cfg_token = QPushButton("⚙ Configurar token")
        self._btn_cfg_token.setStyleSheet(
            f"QPushButton {{ background:{_LOVE}; color:#fff; border:none; "
            f"border-radius:8px; padding:4px 12px; font-size:12px; font-weight:600; }}"
            f"QPushButton:hover {{ background:#9e5269; }}"
        )
        self._btn_cfg_token.setVisible(False)
        self._btn_cfg_token.clicked.connect(self._abrir_ajustes)
        row.addWidget(self._btn_cfg_token)

        row.addStretch()
        return row

    def _abrir_ajustes(self):
        from app.ui.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self)
        dlg.exec_()
        # Re-verificar conexión después de cerrar ajustes
        self._verificar_conexion()

    def _build_cards(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setSpacing(12)

        def card(label, value_id, color):
            frame = QFrame()
            # Borde izquierdo semántico — mismo patrón que dashboard cards
            frame.setStyleSheet(
                f"QFrame {{"
                f"  background:{_SURFACE};"
                f"  border-top: 1px solid #d6cec5;"
                f"  border-right: 1px solid #d6cec5;"
                f"  border-bottom: 1px solid #d6cec5;"
                f"  border-left: 4px solid {color};"
                f"  border-radius: 10px;"
                f"}}"
            )
            lay = QVBoxLayout(frame)
            lay.setContentsMargins(14, 12, 14, 12)
            lay.setSpacing(4)
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color:{_MUTED}; font-size:12px; font-weight:600;")
            val = QLabel("—")
            val.setObjectName(value_id)
            val.setStyleSheet(f"color:{color}; font-size:24px; font-weight:700;")
            lay.addWidget(lbl)
            lay.addWidget(val)
            return frame

        self._card_contactos  = card("Contactos en BD",    "c_contactos",  _PINE)
        self._card_facturas   = card("Facturas en cache",  "c_facturas",   _GOLD)
        self._card_vencidas   = card("Vencidas",           "c_vencidas",   _LOVE)
        self._card_por_vencer = card("Por vencer",         "c_por_vencer", _FOAM)

        grid.addWidget(self._card_contactos,  0, 0)
        grid.addWidget(self._card_facturas,   0, 1)
        grid.addWidget(self._card_vencidas,   1, 0)
        grid.addWidget(self._card_por_vencer, 1, 1)
        return grid

    def _build_facturas_section(self) -> QGroupBox:
        grp = QGroupBox("📥  Importar cartera pendiente")
        lay = QVBoxLayout(grp)
        lay.setSpacing(10)

        info = QLabel(
            "Importa todas las facturas con saldo pendiente desde tu sistema contable.\n"
            "Equivalente a cargar el XLS, pero automático. También actualiza contactos y scores."
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color:{_SUBTLE}; font-size:12px;")
        lay.addWidget(info)

        self._lbl_cache = QLabel(self._texto_cache())
        self._lbl_cache.setStyleSheet(f"color:{_MUTED}; font-size:12px;")
        lay.addWidget(self._lbl_cache)

        row = QHBoxLayout()
        self._btn_sync_facturas = QPushButton("📥  Sincronizar Facturas")
        self._btn_sync_facturas.setProperty("class", "primary")
        self._btn_sync_facturas.setFixedHeight(36)
        self._btn_sync_facturas.clicked.connect(self._iniciar_sync_facturas)
        self._lbl_estado_f = QLabel("")
        self._lbl_estado_f.setStyleSheet(f"color:{_MUTED}; font-size:12px;")
        row.addWidget(self._btn_sync_facturas)
        row.addWidget(self._lbl_estado_f)
        row.addStretch()
        lay.addLayout(row)

        self._progress_f = QProgressBar()
        self._progress_f.setVisible(False)
        self._progress_f.setFixedHeight(6)
        self._progress_f.setTextVisible(False)
        lay.addWidget(self._progress_f)

        self._log_f = QTextEdit()
        self._log_f.setReadOnly(True)
        self._log_f.setMaximumHeight(90)
        self._log_f.setVisible(False)
        self._log_f.setStyleSheet(
            f"font-size:11px; color:{_SUBTLE}; background:{_BG}; "
            f"border:1px solid {_OVERLAY}; border-radius:6px;"
        )
        lay.addWidget(self._log_f)

        return grp

    def _build_contactos_section(self) -> QGroupBox:
        grp = QGroupBox("👥  Sincronizar contactos")
        lay = QVBoxLayout(grp)
        lay.setSpacing(10)

        info = QLabel(
            "Importa email y teléfono de todos tus clientes desde el sistema contable.\n"
            "Abre el diálogo completo con opciones avanzadas."
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color:{_SUBTLE}; font-size:12px;")
        lay.addWidget(info)

        row = QHBoxLayout()
        btn = QPushButton("🔄  Abrir Sincronización de Contactos")
        btn.setProperty("class", "secondary")
        btn.setFixedHeight(36)
        btn.clicked.connect(self._abrir_dialogo_contactos)
        row.addWidget(btn)
        row.addStretch()
        lay.addLayout(row)

        return grp

    # ── Lógica ────────────────────────────────────────────────────────────────

    def refrescar(self):
        """Llamado al activar el tab. Actualiza métricas y estado de conexión."""
        self._actualizar_cards()
        self._verificar_conexion()

    def _actualizar_cards(self):
        contactos = db.get_todos_contactos()
        facturas  = db.get_facturas_cache()
        vencidas  = sum(1 for f in facturas if f.get("tipo") == "vencida")

        self._card_contactos.findChild(QLabel, "c_contactos").setText(str(len(contactos)))
        self._card_facturas.findChild(QLabel, "c_facturas").setText(str(len(facturas)))
        self._card_vencidas.findChild(QLabel, "c_vencidas").setText(str(vencidas))
        self._card_por_vencer.findChild(QLabel, "c_por_vencer").setText(
            str(len(facturas) - vencidas)
        )
        self._lbl_cache.setText(self._texto_cache())

    def _texto_cache(self) -> str:
        facturas = db.get_facturas_cache()
        if not facturas:
            return "ℹ  Sin facturas en cache"
        vencidas = sum(1 for f in facturas if f.get("tipo") == "vencida")
        return (f"Cache actual: {len(facturas)} facturas "
                f"({vencidas} vencidas, {len(facturas)-vencidas} por vencer)")

    def _verificar_conexion(self):
        token = ConfigManager.get().get_contifico().get("api_token", "")
        if not token:
            self._lbl_conn.setText("Token no configurado")
            self._lbl_conn.setStyleSheet(
                f"color:{_LOVE}; font-size:12px; padding:3px 12px; "
                f"border-radius:12px; background:#f9e1e6;"
            )
            self._btn_cfg_token.setVisible(True)
            return
        self._btn_cfg_token.setVisible(False)

        self._lbl_conn.setText("Verificando…")
        self._lbl_conn.setStyleSheet(
            f"color:{_MUTED}; font-size:12px; padding:3px 12px; "
            f"border-radius:12px; background:{_OVERLAY};"
        )

        self._verify_worker = _VerifyWorker(token)
        self._verify_worker.resultado.connect(self._on_verificacion)
        self._verify_worker.start()

    def _on_verificacion(self, ok: bool, msg: str):
        if ok:
            self._lbl_conn.setText(f"✓  {msg}")
            self._lbl_conn.setStyleSheet(
                "color:#286983; font-size:12px; padding:3px 12px; "
                "border-radius:12px; background:#dff0f5;"
            )
        else:
            self._lbl_conn.setText(f"✗  {msg}")
            self._lbl_conn.setStyleSheet(
                f"color:{_LOVE}; font-size:12px; padding:3px 12px; "
                f"border-radius:12px; background:#f9e1e6;"
            )

    def _iniciar_sync_facturas(self):
        token = ConfigManager.get().get_contifico().get("api_token", "")
        if not token:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, "Token requerido",
                "Configura el API token en Ajustes antes de sincronizar."
            )
            return

        self._btn_sync_facturas.setEnabled(False)
        self._btn_sync_facturas.setText("Importando…")
        self._lbl_estado_f.setText("Conectando con la API…")
        self._progress_f.setVisible(True)
        self._progress_f.setRange(0, 0)  # indeterminate
        self._log_f.setVisible(True)
        self._log_f.clear()

        self._worker_f = _SyncFacturasWorker(token)
        self._worker_f.log.connect(self._log_f.append)
        self._worker_f.terminado.connect(self._on_facturas_ok)
        self._worker_f.error.connect(self._on_facturas_error)
        self._worker_f.start()

    def _on_facturas_ok(self, total: int, vencidas: int):
        self._btn_sync_facturas.setEnabled(True)
        self._btn_sync_facturas.setText("📥  Sincronizar Facturas")
        self._progress_f.setRange(0, 1)
        self._progress_f.setValue(1)
        from datetime import datetime
        self._lbl_estado_f.setText(
            f"Última sync: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        )
        self.status_msg.emit(
            f"✓ {total} facturas importadas ({vencidas} vencidas)"
        )
        self._actualizar_cards()
        self.facturas_sincronizadas.emit()

    def _on_facturas_error(self, msg: str):
        self._btn_sync_facturas.setEnabled(True)
        self._btn_sync_facturas.setText("📥  Sincronizar Facturas")
        self._progress_f.setVisible(False)
        self._lbl_estado_f.setText("")
        self.status_msg.emit(f"Error al sincronizar: {msg}")
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.critical(self, "Error al importar facturas", msg)

    def _abrir_dialogo_contactos(self):
        dlg = ContificoDialog(self)
        dlg.contactos_actualizados.connect(self._actualizar_cards)
        dlg.exec_()


# ── Workers ──────────────────────────────────────────────────────────────────

class _VerifyWorker(QThread):
    resultado = pyqtSignal(bool, str)

    def __init__(self, token: str):
        super().__init__()
        self._token = token

    def run(self):
        svc = ContificoService(self._token)
        ok, msg = svc.verificar_conexion()
        self.resultado.emit(ok, msg)


class _SyncFacturasWorker(QThread):
    log       = pyqtSignal(str)
    terminado = pyqtSignal(int, int)
    error     = pyqtSignal(str)

    def __init__(self, token: str):
        super().__init__()
        self._token = token

    def run(self):
        svc = ContificoService(self._token)
        try:
            self.log.emit("Conectando con la API…")
            facturas = svc.get_facturas_pendientes()
        except ContificoError as e:
            self.error.emit(str(e))
            return

        self.log.emit(f"Se encontraron {len(facturas)} facturas. Guardando…")
        db.guardar_facturas_cache(facturas)

        for f in facturas:
            nombre = f.get("cliente", "")
            if nombre:
                db.upsert_contacto(
                    nombre_contifico=nombre,
                    email=f.get("email") or None,
                    telefono=f.get("telefono") or None,
                    fuente="contifico_facturas",
                    confianza=1.0,
                )

        self.log.emit("Actualizando scores…")
        recalcular_todos_los_scores()

        vencidas = sum(1 for f in facturas if f.get("tipo") == "vencida")
        self.log.emit(
            f"✓  Listo: {len(facturas)} facturas "
            f"({vencidas} vencidas, {len(facturas)-vencidas} por vencer)"
        )
        self.terminado.emit(len(facturas), vencidas)
