"""
core/ — Lógica de negocio del Cobrador de Facturas (modo escritorio)

Expone todos los servicios directamente sin depender de HTTP.
La UI llama a estas funciones; no hay servidor de por medio.
"""
from core.database import *          # noqa: F401, F403
from core.config import ConfigManager  # noqa: F401
from core.contifico import ContificoService, ContificoError  # noqa: F401
