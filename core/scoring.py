"""core/scoring.py — Sistema de score y clasificación de clientes."""
from app.services.scoring_service import (  # noqa: F401
    clasificar,
    tono_por_score,
    color_clasificacion,
    calcular_score_cliente,
    recalcular_todos_los_scores,
    get_score_enriquecido,
)
