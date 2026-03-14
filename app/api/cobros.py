"""
api/cobros.py — Endpoints de cartera XLS, mensajes y envio de emails
"""
import tempfile
from pathlib import Path
from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app import database as db
from app.config_manager import ConfigManager
from app.services.cobros_service import parse_reporte, totales
from app.services.email_service import EmailService
from app.services.message_service import MessageService

router = APIRouter(prefix="/cobros")
_msg = MessageService()


def _enriquecer(facturas: list[dict]) -> list[dict]:
    """Normaliza campos y agrega email/telefono desde la BD de contactos."""
    result = []
    for f in facturas:
        contacto = db.get_contacto(f["cliente"]) or {}
        result.append({
            **f,
            "numero":   f.get("factura_no", ""),
            "saldo":    f.get("monto_pendiente", 0),
            "estado":   f.get("tipo", ""),
            "email":    contacto.get("email", ""),
            "telefono": contacto.get("telefono", ""),
        })
    return result


def _cliente_datos(f: dict) -> dict:
    return {
        "cliente":    f.get("cliente", ""),
        "factura_no": f.get("numero", f.get("factura_no", "")),
        "fecha":      f.get("fecha_emision", ""),
        "total":      str(f.get("saldo", f.get("monto_pendiente", ""))),
        "descripcion": f.get("descripcion", ""),
    }


def _email_service() -> EmailService:
    e = ConfigManager.get().get_email()
    return EmailService(e.get("address", ""), e.get("password", ""), e.get("provider", ""))


# ── Cargar XLS ────────────────────────────────────────────────────────────────

@router.post("/cargar-xls")
async def cargar_xls(archivo: UploadFile = File(...)):
    contenido = await archivo.read()
    with tempfile.NamedTemporaryFile(suffix=".xls", delete=False) as tmp:
        tmp.write(contenido)
        tmp_path = tmp.name
    try:
        facturas = parse_reporte(tmp_path)
    except Exception as e:
        raise HTTPException(400, str(e))
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    enriquecidas = _enriquecer(facturas)
    t = totales(facturas)
    stats = {
        "vencido":    t["total_vencido"],
        "por_vencer": t["total_por_vencer"],
        "vigente":    0,
        "total":      round(t["total_vencido"] + t["total_por_vencer"], 2),
    }
    return {"facturas": enriquecidas, "stats": stats}


# ── Generar mensaje ───────────────────────────────────────────────────────────

class MensajeRequest(BaseModel):
    factura: dict


@router.post("/mensaje")
def generar_mensaje(req: MensajeRequest):
    f = req.factura
    tipo = f.get("estado", f.get("tipo", "vencida"))
    asunto, cuerpo = _msg.generar(_cliente_datos(f), tipo=tipo, canal="whatsapp")
    return {"mensaje": cuerpo, "asunto": asunto}


# ── Enviar email individual ───────────────────────────────────────────────────

class EmailRequest(BaseModel):
    factura: dict
    mensaje: str


@router.post("/enviar-email")
def enviar_email(req: EmailRequest):
    f = req.factura
    dest = f.get("email")
    if not dest:
        raise HTTPException(400, "La factura no tiene email registrado")

    svc = _email_service()
    tipo = f.get("estado", f.get("tipo", "vencida"))
    asunto, _ = _msg.generar(_cliente_datos(f), tipo=tipo, canal="email")

    ok, err = svc.enviar([dest], asunto, req.mensaje)
    if not ok:
        raise HTTPException(500, err)

    db.registrar_envio(f.get("numero", f.get("factura_no", "")), f.get("cliente", ""), "email")
    return {"ok": True}


# ── Procesar todo ─────────────────────────────────────────────────────────────

class ProcesarRequest(BaseModel):
    facturas: List[dict]


@router.post("/procesar-todo")
def procesar_todo(req: ProcesarRequest):
    svc = _email_service()
    enviados = errores = 0

    for f in req.facturas:
        if not f.get("email"):
            continue
        if db.ya_fue_enviado_hoy(f.get("numero", f.get("factura_no", "")), "email"):
            continue

        tipo = f.get("estado", f.get("tipo", "vencida"))
        asunto, cuerpo = _msg.generar(_cliente_datos(f), tipo=tipo, canal="email")
        ok, _ = svc.enviar([f["email"]], asunto, cuerpo)

        if ok:
            enviados += 1
            db.registrar_envio(f.get("numero", ""), f.get("cliente", ""), "email")
        else:
            errores += 1

    return {"enviados": enviados, "errores": errores}


# ── Stats y enviados hoy ──────────────────────────────────────────────────────

@router.get("/stats")
def stats():
    return {"vencido": 0, "por_vencer": 0, "total": 0}


@router.get("/enviados-hoy")
def enviados_hoy():
    return db.get_enviados_hoy()
