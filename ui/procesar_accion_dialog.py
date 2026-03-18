"""
ui/procesar_accion_dialog.py — Diálogo para procesar acciones por orden de importancia.

Muestra una acción a la vez (ordenadas riesgoso → medio → confiable),
con selección de tono, canal, y mensaje editable antes de enviar.
"""

import webbrowser
from datetime import date, timedelta

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QFrame, QButtonGroup,
    QMessageBox, QSizePolicy,
)

from app import database as db
from app.config_manager import ConfigManager
from app.services.message_service import MessageService
from app.services.email_service import EmailService

_PINE  = "#286983"
_LOVE  = "#b4637a"
_GOLD  = "#ea9d34"
_FOAM  = "#56949f"
_TEXT  = "#575279"
_MUTED = "#9893a5"
_BG    = "#faf4ed"
_SURF  = "#fffaf3"
_OVR   = "#f2e9e1"

# Tono → tipo de plantilla a usar
_TONO_TIPO = {"amable": "por_vencer", "neutro": None, "firme": "vencida"}
_CLS_TONO  = {"confiable": "amable", "medio": "neutro", "riesgoso": "firme"}
_CLS_COLOR = {"confiable": _PINE,    "medio": _GOLD,   "riesgoso": _LOVE}


def _prioridad(clasificacion: str) -> int:
    return {"riesgoso": 0, "medio": 1, "confiable": 2}.get(clasificacion, 1)


class ProcesarAccionDialog(QDialog):
    """
    Procesa acciones pendientes una por una.

    acciones:      lista de acciones de db.get_acciones_pendientes()
    scores:        dict {cliente: score_dict}
    facturas_idx:  dict {factura_no: factura_dict} construido desde facturas_cache
    start_index:   índice de la acción inicial (para "Modificar" fila específica)
    """

    def __init__(self, acciones: list[dict], scores: dict,
                 facturas_idx: dict, start_index: int = 0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Procesar acciones")
        self.setMinimumSize(600, 520)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        # Ordenar por prioridad (riesgoso primero, luego por score desc)
        self._acciones = sorted(
            acciones,
            key=lambda a: (
                _prioridad(scores.get(a["cliente"], {}).get("clasificacion", "medio")),
                -scores.get(a["cliente"], {}).get("score", 50),
            )
        )
        self._scores      = scores
        self._facturas    = facturas_idx
        self._msg_svc     = MessageService()
        self._idx         = min(start_index, len(self._acciones) - 1)
        self._completadas = 0
        self._enviadas    = 0

        self._build_ui()
        if self._acciones:
            self._mostrar_accion(self._idx)
        else:
            self._mostrar_vacio()

    # ── Construcción ─────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(14)

        # ── Barra de progreso textual ─────────────────────────────────────
        top = QHBoxLayout()
        self._lbl_progreso = QLabel("")
        self._lbl_progreso.setStyleSheet(
            f"font-size:13px; font-weight:600; color:{_TEXT};"
        )
        top.addWidget(self._lbl_progreso)
        top.addStretch()

        self._btn_prev = QPushButton("◀")
        self._btn_prev.setFixedWidth(32)
        self._btn_prev.setStyleSheet(_btn_nav())
        self._btn_prev.clicked.connect(self._anterior)

        self._btn_next = QPushButton("▶")
        self._btn_next.setFixedWidth(32)
        self._btn_next.setStyleSheet(_btn_nav())
        self._btn_next.clicked.connect(self._siguiente_sin_completar)

        top.addWidget(self._btn_prev)
        top.addWidget(self._btn_next)
        root.addLayout(top)

        # ── Tarjeta de cliente ────────────────────────────────────────────
        self._card = QFrame()
        self._card.setStyleSheet(
            f"QFrame {{ background:{_SURF}; border:1px solid {_OVR}; border-radius:10px; }}"
        )
        card_lay = QHBoxLayout(self._card)
        card_lay.setContentsMargins(16, 12, 16, 12)
        card_lay.setSpacing(12)

        info_col = QVBoxLayout()
        info_col.setSpacing(3)
        self._lbl_cliente = QLabel()
        self._lbl_cliente.setStyleSheet(
            f"font-size:16px; font-weight:700; color:{_TEXT}; background:transparent; border:none;"
        )
        self._lbl_factura = QLabel()
        self._lbl_factura.setStyleSheet(
            f"font-size:12px; color:{_MUTED}; background:transparent; border:none;"
        )
        info_col.addWidget(self._lbl_cliente)
        info_col.addWidget(self._lbl_factura)
        card_lay.addLayout(info_col, stretch=1)

        right_col = QVBoxLayout()
        right_col.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        right_col.setSpacing(4)
        self._lbl_monto = QLabel()
        self._lbl_monto.setAlignment(Qt.AlignRight)
        self._lbl_monto.setStyleSheet(
            f"font-size:20px; font-weight:700; color:{_LOVE}; background:transparent; border:none;"
        )
        self._lbl_badge = QLabel()
        self._lbl_badge.setAlignment(Qt.AlignRight)
        self._lbl_badge.setStyleSheet(
            f"font-size:11px; font-weight:600; color:{_MUTED}; background:transparent; border:none;"
        )
        right_col.addWidget(self._lbl_monto)
        right_col.addWidget(self._lbl_badge)
        card_lay.addLayout(right_col)

        root.addWidget(self._card)

        # ── Selectores canal + tono ───────────────────────────────────────
        sel_row = QHBoxLayout()
        sel_row.setSpacing(20)

        sel_row.addWidget(_lbl_sel("Canal:"))
        self._canal_group = QButtonGroup(self)
        self._btn_email = _toggle_btn("📧  Email")
        self._btn_wa    = _toggle_btn("💬  WhatsApp")
        self._canal_group.addButton(self._btn_email, 0)
        self._canal_group.addButton(self._btn_wa,    1)
        self._btn_email.setChecked(True)
        self._canal_group.buttonClicked.connect(lambda _: self._regenerar_mensaje())
        sel_row.addWidget(self._btn_email)
        sel_row.addWidget(self._btn_wa)

        sel_row.addSpacing(16)
        sel_row.addWidget(_lbl_sel("Tono:"))
        self._tono_group = QButtonGroup(self)
        self._btn_amable = _toggle_btn("Amable")
        self._btn_neutro = _toggle_btn("Neutro")
        self._btn_firme  = _toggle_btn("Firme")
        self._tono_group.addButton(self._btn_amable, 0)
        self._tono_group.addButton(self._btn_neutro, 1)
        self._tono_group.addButton(self._btn_firme,  2)
        self._btn_neutro.setChecked(True)
        self._tono_group.buttonClicked.connect(lambda _: self._regenerar_mensaje())
        sel_row.addWidget(self._btn_amable)
        sel_row.addWidget(self._btn_neutro)
        sel_row.addWidget(self._btn_firme)

        sel_row.addStretch()

        btn_regen = QPushButton("↺ Regenerar")
        btn_regen.setStyleSheet(
            f"QPushButton {{ background:{_OVR}; color:{_MUTED}; border:none; "
            f"border-radius:6px; padding:4px 10px; font-size:11px; }}"
            f"QPushButton:hover {{ color:{_TEXT}; background:#e0d7cf; }}"
        )
        btn_regen.clicked.connect(self._regenerar_mensaje)
        sel_row.addWidget(btn_regen)

        root.addLayout(sel_row)

        # ── Editor de mensaje ─────────────────────────────────────────────
        self._editor = QTextEdit()
        self._editor.setStyleSheet(
            f"QTextEdit {{ background:{_SURF}; border:1px solid {_OVR}; "
            f"border-radius:8px; padding:8px; font-size:13px; color:{_TEXT}; }}"
        )
        root.addWidget(self._editor, stretch=1)

        # ── Botones de acción ─────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._btn_posponer = QPushButton("+1 día")
        self._btn_posponer.setStyleSheet(_btn_secondary())
        self._btn_posponer.setToolTip("Posponer esta acción 1 día")
        self._btn_posponer.clicked.connect(self._posponer)

        self._btn_completar = QPushButton("✓ Completar sin enviar")
        self._btn_completar.setStyleSheet(_btn_secondary())
        self._btn_completar.clicked.connect(self._completar_sin_enviar)

        self._btn_enviar = QPushButton("Enviar  ▶")
        self._btn_enviar.setStyleSheet(_btn_primary(_PINE))
        self._btn_enviar.setFixedHeight(36)
        self._btn_enviar.clicked.connect(self._enviar)

        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.setStyleSheet(_btn_secondary())
        btn_cerrar.clicked.connect(self._cerrar_con_resumen)

        btn_row.addWidget(btn_cerrar)
        btn_row.addWidget(self._btn_posponer)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_completar)
        btn_row.addWidget(self._btn_enviar)
        root.addLayout(btn_row)

    # ── Navegación ────────────────────────────────────────────────────────────

    def _mostrar_accion(self, idx: int):
        self._idx = idx
        a = self._acciones[idx]
        total = len(self._acciones)

        self._lbl_progreso.setText(f"Acción {idx + 1} de {total}")
        self._btn_prev.setEnabled(idx > 0)
        self._btn_next.setEnabled(idx < total - 1)

        # Cliente + score
        sc  = self._scores.get(a["cliente"], {})
        cls = sc.get("clasificacion", "medio")
        score_val = sc.get("score", 50)
        tono      = _CLS_TONO.get(cls, "neutro")
        color     = _CLS_COLOR.get(cls, _TEXT)

        self._lbl_cliente.setText(a["cliente"])
        self._lbl_badge.setText(
            f"Score {score_val:.0f}  ·  {cls}  ·  tono: {tono}"
        )
        self._lbl_badge.setStyleSheet(
            f"font-size:11px; font-weight:600; color:{color}; "
            f"background:transparent; border:none;"
        )

        # Factura
        f = self._facturas.get(a.get("factura_no", ""))
        if f:
            monto = f.get("monto_pendiente", 0.0)
            tipo_f = f.get("tipo", "vencida")
            color_monto = _LOVE if tipo_f == "vencida" else _PINE
            self._lbl_monto.setText(f"${monto:,.2f}")
            self._lbl_monto.setStyleSheet(
                f"font-size:20px; font-weight:700; color:{color_monto}; "
                f"background:transparent; border:none;"
            )
            dias = sc.get("dias_promedio_atraso", 0)
            sufijo = f"  ·  {dias:.0f} días prom. atraso" if dias else ""
            self._lbl_factura.setText(
                f"FAC {a.get('factura_no', '—')}  ·  {tipo_f.replace('_', ' ')}{sufijo}"
            )
        else:
            self._lbl_monto.setText("—")
            self._lbl_factura.setText(f"FAC {a.get('factura_no', '—')}")

        # Seleccionar canal por defecto según tipo de acción
        tipo_a = a.get("tipo", "")
        if tipo_a == "contactar_whatsapp":
            self._btn_wa.setChecked(True)
        else:
            self._btn_email.setChecked(True)

        # Seleccionar tono según score
        {"amable": self._btn_amable,
         "neutro": self._btn_neutro,
         "firme":  self._btn_firme}.get(tono, self._btn_neutro).setChecked(True)

        # Generar mensaje
        self._regenerar_mensaje()

    def _mostrar_vacio(self):
        self._lbl_progreso.setText("Sin acciones pendientes")
        self._editor.setPlainText("No hay acciones pendientes para hoy.")
        for btn in (self._btn_enviar, self._btn_completar,
                    self._btn_posponer, self._btn_prev, self._btn_next):
            btn.setEnabled(False)

    def _anterior(self):
        if self._idx > 0:
            self._mostrar_accion(self._idx - 1)

    def _siguiente_sin_completar(self):
        if self._idx < len(self._acciones) - 1:
            self._mostrar_accion(self._idx + 1)

    def _avanzar(self):
        """Avanza a la siguiente acción o cierra si era la última."""
        # Eliminar acción actual de la lista en memoria
        self._acciones.pop(self._idx)
        if not self._acciones:
            self._cerrar_con_resumen()
            return
        # Quedarse en el mismo índice (ahora apunta a la siguiente)
        next_idx = min(self._idx, len(self._acciones) - 1)
        self._mostrar_accion(next_idx)

    # ── Generación de mensaje ─────────────────────────────────────────────────

    def _tono_actual(self) -> str:
        bid = self._tono_group.checkedId()
        return {0: "amable", 1: "neutro", 2: "firme"}.get(bid, "neutro")

    def _canal_actual(self) -> str:
        return "whatsapp" if self._canal_group.checkedId() == 1 else "email"

    def _regenerar_mensaje(self):
        if not self._acciones:
            return
        a     = self._acciones[self._idx]
        tono  = self._tono_actual()
        canal = self._canal_actual()

        f = self._facturas.get(a.get("factura_no", ""))
        if not f:
            # Si no hay factura en cache, usar el mensaje sugerido
            self._editor.setPlainText(a.get("mensaje_sugerido", ""))
            return

        # Mapear tono → tipo de plantilla
        tipo_plantilla = _TONO_TIPO.get(tono) or f.get("tipo", "vencida")

        _, cuerpo = self._msg_svc.generar(f, tipo_plantilla, canal)
        self._editor.setPlainText(cuerpo)

    # ── Acciones ──────────────────────────────────────────────────────────────

    def _enviar(self):
        if not self._acciones:
            return
        a     = self._acciones[self._idx]
        canal = self._canal_actual()
        texto = self._editor.toPlainText().strip()
        if not texto:
            QMessageBox.warning(self, "Mensaje vacío", "Escribe un mensaje antes de enviar.")
            return

        contacto = db.get_contacto(a["cliente"])
        if not contacto:
            QMessageBox.warning(self, "Sin contacto",
                                f"No hay contacto registrado para {a['cliente']}.")
            return

        if canal == "email":
            email = contacto.get("email", "")
            if not email:
                QMessageBox.warning(self, "Sin email",
                                    f"{a['cliente']} no tiene email registrado.")
                return
            cfg = ConfigManager.get().get_email()
            svc = EmailService(cfg["address"], cfg["password"], cfg["provider"])
            f   = self._facturas.get(a.get("factura_no", ""))
            tipo_plantilla = _TONO_TIPO.get(self._tono_actual()) or (
                f.get("tipo", "vencida") if f else "vencida"
            )
            asunto, _ = self._msg_svc.generar(
                f or {"cliente": a["cliente"], "factura_no": a.get("factura_no", "")},
                tipo_plantilla, "email"
            )
            ok, err = svc.enviar([email], asunto, texto)
            if not ok:
                QMessageBox.critical(self, "Error al enviar", err)
                return
            db.registrar_envio(a.get("factura_no", ""), a["cliente"], "email", "ok")
            self._enviadas += 1

        else:  # whatsapp
            tel = contacto.get("telefono", "")
            if not tel:
                QMessageBox.warning(self, "Sin teléfono",
                                    f"{a['cliente']} no tiene teléfono registrado.")
                return
            url = self._msg_svc.generar_url_whatsapp(tel, texto)
            webbrowser.open(url)
            db.registrar_envio(a.get("factura_no", ""), a["cliente"], "whatsapp", "ok")
            self._enviadas += 1

        db.completar_accion(a["id"])
        self._completadas += 1
        self._avanzar()

    def _completar_sin_enviar(self):
        if not self._acciones:
            return
        a = self._acciones[self._idx]
        db.completar_accion(a["id"])
        self._completadas += 1
        self._avanzar()

    def _posponer(self):
        if not self._acciones:
            return
        a    = self._acciones[self._idx]
        nueva = (date.today() + timedelta(days=1)).isoformat()
        db.posponer_accion(a["id"], nueva)
        self._avanzar()

    def _cerrar_con_resumen(self):
        if self._completadas > 0 or self._enviadas > 0:
            QMessageBox.information(
                self, "Sesión completada",
                f"Resumen:\n"
                f"  Enviados:   {self._enviadas}\n"
                f"  Completados (sin envío): {self._completadas - self._enviadas}\n"
                f"  Total procesados: {self._completadas}"
            )
        self.accept()


# ── Helpers de estilos ────────────────────────────────────────────────────────

def _lbl_sel(text: str) -> QLabel:
    l = QLabel(text)
    l.setStyleSheet(f"font-size:12px; color:{_MUTED}; font-weight:600;")
    return l


def _toggle_btn(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setCheckable(True)
    btn.setStyleSheet(
        f"QPushButton {{ background:{_OVR}; color:{_TEXT}; border:none; "
        f"border-radius:6px; padding:4px 12px; font-size:12px; }}"
        f"QPushButton:checked {{ background:{_PINE}; color:#fff; font-weight:600; }}"
        f"QPushButton:hover:!checked {{ background:#e0d7cf; }}"
    )
    return btn


def _btn_primary(color: str) -> str:
    return (f"QPushButton {{ background:{color}; color:#fff; border:none; "
            f"border-radius:8px; padding:6px 20px; font-size:13px; font-weight:600; }}"
            f"QPushButton:hover {{ background:#1d4f63; }}"
            f"QPushButton:disabled {{ background:{_OVR}; color:{_MUTED}; }}")


def _btn_secondary() -> str:
    return (f"QPushButton {{ background:{_OVR}; color:{_TEXT}; border:none; "
            f"border-radius:8px; padding:6px 14px; font-size:12px; }}"
            f"QPushButton:hover {{ background:#e0d7cf; }}")


def _btn_nav() -> str:
    return (f"QPushButton {{ background:{_OVR}; color:{_TEXT}; border:none; "
            f"border-radius:6px; font-size:13px; }}"
            f"QPushButton:hover {{ background:#e0d7cf; }}"
            f"QPushButton:disabled {{ color:{_MUTED}; background:{_OVR}; }}")
