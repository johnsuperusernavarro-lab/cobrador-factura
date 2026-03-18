"""
cotizacion_service.py — Lógica de negocio para el módulo de Cotizaciones.

Genera mensajes de cotización (email / WhatsApp) a partir de los datos
de la cotización y sus ítems. Reutiliza ConfigManager para datos del remitente.
"""

import urllib.parse
from datetime import datetime, timedelta

from app.config_manager import ConfigManager


# ─── Formateo de ítems ────────────────────────────────────────────────────────

def _formatear_items_texto(items: list[dict]) -> str:
    """Renderiza la tabla de ítems como texto plano alineado."""
    if not items:
        return "  (sin ítems)"
    lines = []
    for i in items:
        desc   = i.get("descripcion", "")
        cant   = float(i.get("cantidad", 1))
        precio = float(i.get("precio_unit", 0))
        total  = float(i.get("total", cant * precio))
        cant_s = f"{cant:g}"
        lines.append(
            f"  • {desc:<35} {cant_s:>4} x ${precio:>8.2f}  =  ${total:>9.2f}"
        )
    return "\n".join(lines)


def _formatear_items_whatsapp(items: list[dict]) -> str:
    """Renderiza la tabla de ítems con formato WhatsApp (asteriscos)."""
    if not items:
        return "  (sin ítems)"
    lines = []
    for i in items:
        desc   = i.get("descripcion", "")
        cant   = float(i.get("cantidad", 1))
        precio = float(i.get("precio_unit", 0))
        total  = float(i.get("total", cant * precio))
        cant_s = f"{cant:g}"
        lines.append(f"  • {desc}  ({cant_s} x ${precio:.2f}) = *${total:.2f}*")
    return "\n".join(lines)


# ─── Generación de mensajes ───────────────────────────────────────────────────

def generar_mensaje_cotizacion(cotizacion: dict, items: list[dict],
                                canal: str) -> tuple[str, str]:
    """
    Genera (asunto, cuerpo) para una cotización.

    canal: 'email' | 'whatsapp'
    Retorna ('', cuerpo) para WhatsApp (sin asunto).
    """
    cfg     = ConfigManager.get()
    rem     = cfg.get_remitente()
    ema     = cfg.get_email()
    wa_cfg  = cfg.get_whatsapp()

    nombre   = rem.get("nombre", "[TU NOMBRE]")
    empresa  = rem.get("empresa", "[TU EMPRESA]")
    cargo    = rem.get("cargo", "")
    telefono = wa_cfg.get("mi_telefono", "")
    correo   = ema.get("address", "")

    cliente    = cotizacion.get("cliente", "")
    total      = float(cotizacion.get("total", 0))
    validez    = int(cotizacion.get("validez_dias", 30))
    notas      = cotizacion.get("notas") or ""
    fecha_hoy  = datetime.now().strftime("%d/%m/%Y")
    cot_id     = cotizacion.get("id", "")

    fecha_validez = (datetime.now() + timedelta(days=validez)).strftime("%d/%m/%Y")

    if canal == "email":
        items_txt = _formatear_items_texto(items)
        asunto = f"Cotización N° {cot_id} — {empresa}"
        cuerpo = (
            f"Estimados señores {cliente},\n\n"
            f"Por medio del presente les hacemos llegar nuestra cotización "
            f"N° {cot_id}, con fecha {fecha_hoy}.\n\n"
            f"{'─'*55}\n"
            f"DETALLE DE SERVICIOS / PRODUCTOS\n"
            f"{'─'*55}\n"
            f"{items_txt}\n"
            f"{'─'*55}\n"
            f"TOTAL:  ${total:,.2f}\n"
            f"{'─'*55}\n\n"
            f"Esta cotización tiene validez hasta el {fecha_validez}.\n"
        )
        if notas:
            cuerpo += f"\nObservaciones:\n{notas}\n"
        cuerpo += (
            f"\nQuedamos a su entera disposición para cualquier consulta.\n\n"
            f"Saludos cordiales,\n\n"
            f"{nombre}\n"
            f"{empresa}{' — ' + cargo if cargo else ''}\n"
            f"Tel: {telefono}  |  Email: {correo}\n"
        )
        return asunto, cuerpo

    else:  # whatsapp
        items_txt = _formatear_items_whatsapp(items)
        cuerpo = (
            f"Estimados *{cliente}*,\n\n"
            f"Les comparto la cotización *N° {cot_id}* con fecha {fecha_hoy}.\n\n"
            f"📋 *DETALLE:*\n"
            f"{items_txt}\n\n"
            f"💰 *TOTAL: ${total:,.2f}*\n\n"
            f"⏳ Válida hasta: {fecha_validez}\n"
        )
        if notas:
            cuerpo += f"\n📝 {notas}\n"
        cuerpo += (
            f"\nQuedo atento a cualquier consulta. 🤝\n\n"
            f"*{nombre}*\n"
            f"{empresa}\n"
            f"{telefono}"
        )
        return "", cuerpo


def generar_url_whatsapp(telefono: str, mensaje: str) -> str:
    """Construye URL wa.me con mensaje prellenado. Normaliza número ecuatoriano."""
    tel = telefono.strip().replace(" ", "").replace("-", "")
    if tel.startswith("0"):
        tel = "593" + tel[1:]
    elif not tel.startswith("593"):
        tel = "593" + tel
    return f"https://wa.me/{tel}?text={urllib.parse.quote(mensaje)}"
