"""
api/contifico_api.py — Sincronizacion de contactos desde la API de Contifico
"""
from fastapi import APIRouter, HTTPException

from app import database as db
from app.config_manager import ConfigManager
from app.services.contifico_service import ContificoService, ContificoError

router = APIRouter(prefix="/contifico")


@router.get("/contactos")
def get_contactos():
    return db.get_todos_contactos()


@router.post("/sincronizar")
def sincronizar():
    cfg = ConfigManager.get().get_contifico()
    token = cfg.get("api_token", "")
    if not token:
        raise HTTPException(400, "Configura el token de Contifico en Ajustes antes de sincronizar")

    svc = ContificoService(token)
    try:
        clientes = svc.get_clientes()
    except ContificoError as e:
        raise HTTPException(502, str(e))

    nuevos = actualizados = 0
    for c in clientes:
        nombre = c.get("razon_social", "").strip()
        if not nombre:
            continue
        existente = db.get_contacto(nombre)
        db.upsert_contacto(
            nombre_contifico = nombre,
            email    = c.get("email", ""),
            telefono = c.get("telefono", ""),
        )
        if existente:
            actualizados += 1
        else:
            nuevos += 1

    return {"nuevos": nuevos, "actualizados": actualizados, "total": len(clientes)}
