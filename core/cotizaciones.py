"""
core/cotizaciones.py — Re-exporta cotizacion_service para uso desde ui/.
"""
from app.services.cotizacion_service import (   # noqa: F401
    generar_mensaje_cotizacion,
    generar_url_whatsapp,
)
