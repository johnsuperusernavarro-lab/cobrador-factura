"""core/automation.py — Motor de automatización y scheduler."""
from app.services.automation_service import (  # noqa: F401
    evaluar_facturas,
    activar,
    desactivar,
    esta_activo,
    estado,
    restaurar_si_estaba_activo,
)
