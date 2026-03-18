"""
config_manager.py — Configuración persistente de la aplicación (data/config.json)
"""

import copy
import json
from pathlib import Path

from app.utils import get_data_dir

_CONFIG_PATH = get_data_dir() / "config.json"

_DEFAULTS: dict = {
    "provider": {
        "type":      "contifico",   # contifico | alegra | excel
        "api_token": "",            # contifico
        "email":     "",            # alegra
        "token":     "",            # alegra
        "template":  "",            # excel: nombre del template en data/templates/
    },
    "email": {
        "provider": "gmail",
        "address":  "",
        "password": "",
    },
    "whatsapp": {
        "mi_telefono": "",
    },
    "contifico": {
        "api_token": "",
    },
    "remitente": {
        "nombre":  "",
        "empresa": "",
        "cargo":   "",
    },
    "banco": {
        "nombre":   "",
        "titular":  "",
        "numero":   "",
        "tipo":     "Cta. Corriente",
        "ci":       "",
    },
}


class ConfigManager:
    """Singleton que lee/escribe data/config.json."""

    _instance: "ConfigManager | None" = None

    @classmethod
    def get(cls) -> "ConfigManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._data = copy.deepcopy(_DEFAULTS)
        self._load()

    # ── Persistencia ──────────────────────────────────────────────────────

    def _load(self):
        if not _CONFIG_PATH.exists():
            return
        try:
            with open(_CONFIG_PATH, encoding="utf-8") as f:
                loaded: dict = json.load(f)
            for section, vals in loaded.items():
                if section in self._data and isinstance(vals, dict):
                    self._data[section].update(vals)
                else:
                    self._data[section] = vals
        except Exception:
            pass  # Config corrupta: usar defaults

    def save(self):
        _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    # ── Email ─────────────────────────────────────────────────────────────

    def get_email(self) -> dict:
        return dict(self._data["email"])

    def set_email(self, provider: str, address: str, password: str):
        self._data["email"] = {
            "provider": provider,
            "address":  address,
            "password": password,
        }

    # ── WhatsApp ──────────────────────────────────────────────────────────

    def get_whatsapp(self) -> dict:
        return dict(self._data["whatsapp"])

    def set_whatsapp(self, mi_telefono: str):
        self._data["whatsapp"]["mi_telefono"] = mi_telefono

    # ── Contifico ─────────────────────────────────────────────────────────

    def get_contifico(self) -> dict:
        return dict(self._data.get("contifico", {"api_token": ""}))

    def set_contifico(self, api_token: str):
        self._data["contifico"] = {"api_token": api_token}

    # ── Remitente ─────────────────────────────────────────────────────────

    def get_remitente(self) -> dict:
        return dict(self._data.get("remitente", _DEFAULTS["remitente"]))

    def set_remitente(self, nombre: str, empresa: str, cargo: str):
        self._data["remitente"] = {
            "nombre":  nombre,
            "empresa": empresa,
            "cargo":   cargo,
        }

    # ── Banco ─────────────────────────────────────────────────────────────

    def get_banco(self) -> dict:
        return dict(self._data.get("banco", _DEFAULTS["banco"]))

    def set_banco(self, nombre: str, titular: str, numero: str, tipo: str, ci: str):
        self._data["banco"] = {
            "nombre":  nombre,
            "titular": titular,
            "numero":  numero,
            "tipo":    tipo,
            "ci":      ci,
        }

    # ── Proveedor contable ────────────────────────────────────────────────

    def get_provider(self) -> dict:
        """Retorna la config del proveedor contable activo."""
        cfg = dict(self._data.get("provider", _DEFAULTS["provider"]))
        # Compatibilidad: si hay token de Contifico y el tipo es contifico,
        # usar ese token aunque esté en la sección legacy "contifico".
        if cfg.get("type") == "contifico" and not cfg.get("api_token"):
            cfg["api_token"] = self._data.get("contifico", {}).get("api_token", "")
        return cfg

    def set_provider(self, tipo: str, **kwargs):
        self._data["provider"] = {"type": tipo, **kwargs}
