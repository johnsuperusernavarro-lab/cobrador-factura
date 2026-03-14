"""
api/config_api.py — Endpoints de configuracion (lectura y guardado)
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Any

from app.config_manager import ConfigManager

router = APIRouter(prefix="/config")


@router.get("")
def get_config():
    """Devuelve la configuracion actual (sin la contrasena de email)."""
    cfg = ConfigManager.get()
    data = {
        "email":     cfg.get_email(),
        "whatsapp":  cfg.get_whatsapp(),
        "contifico": cfg.get_contifico(),
        "remitente": cfg.get_remitente(),
        "banco":     cfg.get_banco(),
    }
    # Ocultar contrasena
    data["email"] = {k: v for k, v in data["email"].items() if k != "password"}
    return data


@router.post("")
def save_config(body: dict):
    """Guarda la configuracion. Acepta parcialmente cualquier seccion."""
    cfg = ConfigManager.get()

    if "email" in body:
        e = body["email"]
        current = cfg.get_email()
        cfg.set_email(
            provider = e.get("provider", current.get("provider", "gmail")),
            address  = e.get("address",  current.get("address",  "")),
            password = e.get("password", current.get("password", "")) or current.get("password", ""),
        )

    if "whatsapp" in body:
        cfg.set_whatsapp(body["whatsapp"].get("mi_telefono", ""))

    if "contifico" in body:
        cfg.set_contifico(body["contifico"].get("api_token", ""))

    if "remitente" in body:
        r = body["remitente"]
        cfg.set_remitente(
            nombre  = r.get("nombre", ""),
            empresa = r.get("empresa", ""),
            cargo   = r.get("cargo", ""),
        )

    if "banco" in body:
        b = body["banco"]
        cfg.set_banco(
            nombre   = b.get("nombre", ""),
            titular  = b.get("titular", ""),
            numero   = b.get("numero", ""),
            tipo     = b.get("tipo", "Cta. Corriente"),
            ci       = b.get("ci", ""),
        )

    cfg.save()
    return {"ok": True}


@router.get("/resumen")
def resumen():
    """Resumen minimo para la UI (empresa, email configurado)."""
    cfg = ConfigManager.get()
    return {
        "empresa":         cfg.get_remitente().get("empresa", ""),
        "email_ok":        bool(cfg.get_email().get("address")),
        "contifico_ok":    bool(cfg.get_contifico().get("api_token")),
    }
