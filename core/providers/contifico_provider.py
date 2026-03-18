"""
core/providers/contifico_provider.py — Adaptador Contifico.

Envuelve ContificoService en la interfaz estándar AccountingProvider.
No duplica lógica: toda la implementación real sigue en app/services/contifico_service.py.

Configuración esperada:
  {"type": "contifico", "api_token": "<token>"}
"""

from core.base_provider import AccountingProvider, ProviderError
from app.services.contifico_service import ContificoService, ContificoError


class ContificoProvider(AccountingProvider):

    def __init__(self, cfg: dict):
        token = cfg.get("api_token", "")
        if not token:
            raise ProviderError("Contifico requiere 'api_token' en la configuración.")
        self._svc = ContificoService(token)

    @property
    def nombre(self) -> str:
        return "Contifico"

    def verificar_conexion(self) -> tuple[bool, str]:
        try:
            return self._svc.verificar_conexion()
        except ContificoError as e:
            return False, str(e)

    def get_cartera(self, progreso_cb=None) -> list[dict]:
        try:
            return self._svc.get_facturas_pendientes(progreso_cb=progreso_cb)
        except ContificoError as e:
            raise ProviderError(str(e)) from e

    def get_contactos(self, progreso_cb=None) -> list[dict]:
        try:
            return self._svc.get_clientes(progreso_cb=progreso_cb)
        except ContificoError as e:
            raise ProviderError(str(e)) from e
