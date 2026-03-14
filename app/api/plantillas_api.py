"""
api/plantillas_api.py — CRUD de plantillas de mensajes
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import database as db

router = APIRouter(prefix="/plantillas")


@router.get("")
def get_plantillas():
    return db.get_todas_plantillas()


class PlantillaIn(BaseModel):
    tipo:   str
    canal:  str
    asunto: str = ""
    cuerpo: str = ""


@router.post("")
def save_plantilla(body: PlantillaIn):
    TIPOS_VALIDOS  = {"vencida", "por_vencer", "pdf"}
    CANALES_VALIDOS = {"email", "whatsapp"}

    if body.tipo not in TIPOS_VALIDOS:
        raise HTTPException(400, f"tipo debe ser uno de: {TIPOS_VALIDOS}")
    if body.canal not in CANALES_VALIDOS:
        raise HTTPException(400, f"canal debe ser uno de: {CANALES_VALIDOS}")

    db.save_plantilla(body.tipo, body.canal, body.asunto, body.cuerpo)
    return {"ok": True}
