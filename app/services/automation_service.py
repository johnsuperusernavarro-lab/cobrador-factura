"""
automation_service.py — Motor de Automatización y Scheduler

Ejecuta evaluaciones periódicas de facturas, aplica reglas de cobranza
y genera acciones sugeridas. Funciona como un thread daemon en segundo plano.
"""

import queue
import threading
import logging
from datetime import date, timedelta

from app import database as db
from app.services.scoring_service import (
    calcular_score_cliente,
    recalcular_todos_los_scores,
)

logger = logging.getLogger(__name__)


def _parse_fecha_cartera(s: str) -> date | None:
    """Parsea DD/MM/YYYY (formato interno) o YYYY-MM-DD. Retorna None si falla."""
    if not s:
        return None
    s = s.strip()
    if "/" in s:
        try:
            d, m, y = s.split("/")
            return date(int(y), int(m), int(d))
        except Exception:
            return None
    try:
        return date.fromisoformat(s[:10])
    except Exception:
        return None


# ─── Estado del scheduler ───────────────────────────────────────────────────

_stop_event = threading.Event()
_thread: threading.Thread | None = None
_INTERVALO_HORAS = 1  # Evaluar cada hora

# Cola thread-safe para comunicar eventos al hilo Qt
_eventos_ui: queue.Queue = queue.Queue()


def _push_evento(tipo: str, datos: dict):
    """Publica un evento para que el hilo Qt lo consuma con pop_eventos()."""
    from datetime import datetime
    _eventos_ui.put({"tipo": tipo, "datos": datos, "ts": datetime.now().isoformat()})


def pop_eventos() -> list[dict]:
    """Drena todos los eventos pendientes. Llamar desde el hilo Qt (QTimer)."""
    eventos = []
    try:
        while True:
            eventos.append(_eventos_ui.get_nowait())
    except queue.Empty:
        pass
    return eventos


# ─── Motor de reglas ─────────────────────────────────────────────────────────

def evaluar_facturas() -> dict:
    """
    Analiza facturas_cache, actualiza scores y genera acciones sugeridas.
    Retorna resumen de la evaluación.
    """
    facturas = db.get_facturas_cache()
    if not facturas:
        return {"evaluadas": 0, "acciones_creadas": 0, "scores_actualizados": 0}

    hoy = date.today().isoformat()
    scores_actualizados = recalcular_todos_los_scores()

    # Agrupar por cliente para consultar su score
    por_cliente: dict[str, list[dict]] = {}
    for f in facturas:
        por_cliente.setdefault(f["cliente"], []).append(f)

    acciones_creadas = 0
    db.limpiar_acciones_antiguas()

    for f in facturas:
        cliente = f["cliente"]
        factura_no = f.get("factura_no") or f.get("numero", "")
        tipo = f.get("tipo", "")
        fv_str = f.get("fecha_vencimiento", "")

        # Evitar duplicar acción pendiente para la misma factura hoy
        if db.hay_accion_pendiente_hoy(cliente, factura_no):
            continue

        score_row = db.get_score(cliente)
        score = score_row["score"] if score_row else 50.0
        cls = score_row["clasificacion"] if score_row else "medio"

        # Calcular días de atraso
        dias_atraso = 0
        fv = _parse_fecha_cartera(fv_str)
        if fv:
            dias_atraso = (date.today() - fv).days

        # ── Regla 1: Facturas vencidas ────────────────────────────────────
        if tipo == "vencida":
            if cls == "riesgoso":
                prioridad = 1  # Alta
                accion_tipo = "contactar_email"
                msg = (f"URGENTE: {cliente} — Factura {factura_no} vencida hace "
                       f"{dias_atraso} días. Cliente clasificado como RIESGOSO.")
            elif cls == "medio":
                prioridad = 2
                accion_tipo = "contactar_email"
                msg = (f"{cliente} — Factura {factura_no} vencida hace {dias_atraso} días.")
            else:
                prioridad = 3
                accion_tipo = "contactar_whatsapp"
                msg = (f"{cliente} — Factura {factura_no} vencida. "
                       f"Cliente confiable, recordatorio amable.")

            db.crear_accion(cliente, factura_no, accion_tipo, prioridad, msg, hoy)
            acciones_creadas += 1

        # ── Regla 2: Por vencer en <= 3 días ──────────────────────────────
        elif tipo == "por_vencer" and fv_str:
            fv2 = _parse_fecha_cartera(fv_str)
            if fv2:
                dias_restantes = (fv2 - date.today()).days
                if 0 <= dias_restantes <= 3:
                    prioridad = 3 if cls == "riesgoso" else 4
                    accion_tipo = "contactar_email"
                    msg = (f"{cliente} — Factura {factura_no} vence en "
                           f"{dias_restantes} día(s). Enviar recordatorio preventivo.")
                    db.crear_accion(cliente, factura_no, accion_tipo, prioridad, msg, hoy)
                    acciones_creadas += 1

    # Detectar nuevas facturas vencidas respecto al ciclo anterior
    n_vencidas_actual = sum(1 for f in facturas if f.get("tipo") == "vencida")
    n_vencidas_previo = int(db.get_config_sistema("n_vencidas_ultimo_ciclo", "0"))
    if n_vencidas_actual > n_vencidas_previo:
        _push_evento("nuevas_vencidas", {
            "n_total":  n_vencidas_actual,
            "n_nuevas": n_vencidas_actual - n_vencidas_previo,
        })
    db.set_config_sistema("n_vencidas_ultimo_ciclo", str(n_vencidas_actual))

    logger.info(
        "Evaluación: %d facturas, %d acciones creadas, %d scores actualizados",
        len(facturas), acciones_creadas, scores_actualizados,
    )
    return {
        "evaluadas": len(facturas),
        "acciones_creadas": acciones_creadas,
        "scores_actualizados": scores_actualizados,
        "timestamp": date.today().isoformat(),
    }


# ─── Scheduler ───────────────────────────────────────────────────────────────

def _loop():
    logger.info("Scheduler iniciado (intervalo: %dh)", _INTERVALO_HORAS)
    while not _stop_event.is_set():
        try:
            evaluar_facturas()
        except Exception as exc:
            logger.error("Error en evaluación automática: %s", exc)
        # Esperar el intervalo (interrumpible por stop_event)
        _stop_event.wait(timeout=_INTERVALO_HORAS * 3600)
    logger.info("Scheduler detenido")


def activar() -> bool:
    """Activa el Modo Inteligente. Retorna True si se inició."""
    global _thread
    if _thread and _thread.is_alive():
        return False  # Ya estaba activo

    _stop_event.clear()
    db.set_config_sistema("modo_inteligente", "1")

    _thread = threading.Thread(target=_loop, name="AutomationScheduler", daemon=True)
    _thread.start()
    return True


def desactivar() -> bool:
    """Desactiva el Modo Inteligente. Retorna True si estaba activo."""
    global _thread
    db.set_config_sistema("modo_inteligente", "0")
    if _thread and _thread.is_alive():
        _stop_event.set()
        return True
    return False


def esta_activo() -> bool:
    return bool(_thread and _thread.is_alive() and not _stop_event.is_set())


def estado() -> dict:
    activo = esta_activo()
    facturas = db.get_facturas_cache()
    pendientes = db.get_acciones_pendientes(date.today().isoformat())
    return {
        "activo": activo,
        "facturas_en_cache": len(facturas),
        "acciones_pendientes_hoy": len(pendientes),
        "intervalo_horas": _INTERVALO_HORAS,
    }


def restaurar_si_estaba_activo():
    """Llamar al iniciar la app: si el modo estaba activo, lo reactiva."""
    valor = db.get_config_sistema("modo_inteligente", "0")
    if valor == "1":
        activar()
