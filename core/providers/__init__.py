"""
core/providers/ — Adaptadores para sistemas contables.

Uso:
    from core.providers import get_provider
    provider = get_provider()           # lee config automáticamente
    facturas = provider.get_cartera()

Para registrar un nuevo proveedor:
    1. Crea core/providers/mi_sistema_provider.py (hereda AccountingProvider)
    2. Agrega una entrada en _REGISTRY
"""

from core.base_provider import AccountingProvider, ProviderError  # noqa: F401


# ── Registro de proveedores disponibles ───────────────────────────────────────
# clave: valor de config["provider"]["type"]
# valor: función importadora lazy (evita importar todos al arrancar)

def _load_contifico():
    from core.providers.contifico_provider import ContificoProvider
    return ContificoProvider

def _load_excel():
    from core.providers.excel_provider import ExcelProvider
    return ExcelProvider

def _load_alegra():
    from core.providers.alegra_provider import AlegraProvider
    return AlegraProvider


_REGISTRY = {
    "contifico": _load_contifico,
    "excel":     _load_excel,
    "alegra":    _load_alegra,
}


def get_provider(cfg: dict | None = None) -> AccountingProvider:
    """
    Devuelve una instancia del proveedor configurado.

    cfg debe tener:
      {"type": "contifico", "api_token": "..."}
      {"type": "excel", "template": "contifico_xls"}
      {"type": "alegra", "email": "...", "token": "..."}

    Si cfg es None, lo lee desde ConfigManager.
    """
    if cfg is None:
        from app.config_manager import ConfigManager
        cfg = ConfigManager.get().get_provider()

    tipo = cfg.get("type", "contifico")

    loader = _REGISTRY.get(tipo)
    if loader is None:
        raise ProviderError(
            f"Proveedor desconocido: '{tipo}'. "
            f"Disponibles: {list(_REGISTRY.keys())}"
        )

    ProviderClass = loader()
    return ProviderClass(cfg)


def proveedores_disponibles() -> list[str]:
    """Retorna los nombres de todos los proveedores registrados."""
    return list(_REGISTRY.keys())
