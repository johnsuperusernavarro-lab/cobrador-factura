"""
scoring_service.py — Sistema de Score de Cliente

Score 0-100 donde 0 = muy confiable, 100 = muy riesgoso.
Clasificación: confiable (0-35), medio (36-65), riesgoso (66-100).
Tono del mensaje: amable / neutro / firme.
"""

from datetime import date, datetime
from app import database as db


# ─── Clasificación ───────────────────────────────────────────────────────────

def clasificar(score: float) -> str:
    if score <= 35:
        return "confiable"
    elif score <= 65:
        return "medio"
    return "riesgoso"


def tono_por_score(score: float) -> str:
    if score <= 35:
        return "amable"
    elif score <= 65:
        return "neutro"
    return "firme"


def color_clasificacion(clasificacion: str) -> str:
    return {"confiable": "pine", "medio": "gold", "riesgoso": "love"}.get(clasificacion, "muted")


# ─── Cálculo de score ────────────────────────────────────────────────────────

def _dias_vencida(fecha_vencimiento: str) -> int:
    """Retorna días de atraso (positivo). Soporta DD/MM/YYYY e ISO YYYY-MM-DD."""
    if not fecha_vencimiento:
        return 0
    s = fecha_vencimiento.strip()
    try:
        if "/" in s:
            d, m, y = s.split("/")
            fv = date(int(y), int(m), int(d))
        else:
            fv = date.fromisoformat(s[:10])
        return (date.today() - fv).days
    except Exception:
        return 0


def calcular_score_cliente(facturas_cliente: list[dict]) -> dict:
    """
    Calcula el score de un cliente a partir de sus facturas activas.

    Lógica de puntuación:
    - Base: 30 puntos (neutral-bajo)
    - +15 por cada factura vencida
    - +0.5 por cada día promedio de atraso
    - +10 si tiene > 2 facturas vencidas simultáneas
    - Máximo: 100
    """
    if not facturas_cliente:
        return {"score": 30.0, "clasificacion": "confiable",
                "dias_promedio": 0.0, "total": 0, "vencidas": 0}

    total = len(facturas_cliente)
    vencidas = [f for f in facturas_cliente if f.get("tipo") == "vencida"]
    n_vencidas = len(vencidas)

    dias_list = []
    for f in vencidas:
        dias = _dias_vencida(f.get("fecha_vencimiento", ""))
        if dias > 0:
            dias_list.append(dias)

    dias_promedio = sum(dias_list) / len(dias_list) if dias_list else 0.0

    score = 30.0
    score += n_vencidas * 15
    score += dias_promedio * 0.5
    if n_vencidas > 2:
        score += 10

    score = min(100.0, round(score, 1))
    cls = clasificar(score)

    return {
        "score": score,
        "clasificacion": cls,
        "dias_promedio": round(dias_promedio, 1),
        "total": total,
        "vencidas": n_vencidas,
    }


# ─── Actualización masiva ────────────────────────────────────────────────────

def recalcular_todos_los_scores() -> int:
    """
    Recalcula el score de todos los clientes presentes en facturas_cache.
    Retorna la cantidad de clientes actualizados.
    """
    facturas = db.get_facturas_cache()
    if not facturas:
        return 0

    # Agrupar por cliente
    por_cliente: dict[str, list[dict]] = {}
    for f in facturas:
        cliente = f["cliente"]
        por_cliente.setdefault(cliente, []).append(f)

    for cliente, fs in por_cliente.items():
        resultado = calcular_score_cliente(fs)
        db.upsert_score(
            cliente=cliente,
            score=resultado["score"],
            clasificacion=resultado["clasificacion"],
            dias_promedio=resultado["dias_promedio"],
            total=resultado["total"],
            vencidas=resultado["vencidas"],
        )

    return len(por_cliente)


def get_score_enriquecido(cliente: str) -> dict:
    """Retorna el score de un cliente con campos calculados adicionales."""
    row = db.get_score(cliente)
    if not row:
        return {
            "cliente": cliente,
            "score": 50.0,
            "clasificacion": "medio",
            "tono": "neutro",
            "color": "gold",
            "dias_promedio_atraso": 0.0,
            "total_facturas": 0,
            "facturas_vencidas": 0,
        }
    row["tono"] = tono_por_score(row["score"])
    row["color"] = color_clasificacion(row["clasificacion"])
    return row
