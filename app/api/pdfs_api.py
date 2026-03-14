"""
api/pdfs_api.py — Extraccion de datos de RIDEs y envio por email
"""
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.config_manager import ConfigManager
from app.services.email_service import EmailService
from app.services.message_service import MessageService
from app.services.pdf_extractor import extraer_datos

router = APIRouter(prefix="/pdfs")
_msg = MessageService()


@router.post("/extraer")
async def extraer(archivo: UploadFile = File(...)):
    if not archivo.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Solo se aceptan archivos PDF")

    contenido = await archivo.read()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(contenido)
        tmp_path = tmp.name

    try:
        datos = extraer_datos(Path(tmp_path))
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    # Agregar primer email encontrado como campo plano
    emails = datos.get("emails", [])
    datos["email"] = emails[0] if emails else ""
    datos["cliente"] = datos.get("razon_social", "")
    datos["numero"]  = datos.get("factura_no", "")

    # Generar mensaje desde plantilla
    asunto, cuerpo = _msg.generar(
        cliente_datos={
            "cliente":    datos.get("razon_social", ""),
            "factura_no": datos.get("factura_no", ""),
            "fecha":      datos.get("fecha", ""),
            "total":      datos.get("total", ""),
            "descripcion": datos.get("descripcion", ""),
        },
        tipo="pdf",
        canal="email",
    )
    datos["mensaje"] = cuerpo
    datos["asunto"]  = asunto

    return datos


class EmailPDFRequest(BaseModel):
    datos:   dict
    mensaje: str


@router.post("/enviar-email")
def enviar_email(req: EmailPDFRequest):
    dest = req.datos.get("email")
    if not dest:
        raise HTTPException(400, "No se encontro email en el PDF")

    e = ConfigManager.get().get_email()
    svc = EmailService(e.get("address", ""), e.get("password", ""), e.get("provider", ""))
    asunto = req.datos.get("asunto", "Factura")

    ok, err = svc.enviar([dest], asunto, req.mensaje)
    if not ok:
        raise HTTPException(500, err)
    return {"ok": True}
