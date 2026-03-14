#!/usr/bin/env python3
"""
COBRADOR DE FACTURAS - INTERBALANZAS DEL ECUADOR
=================================================
Procesa las carpetas 'por_vencer' y 'vencidas', envia emails
automaticamente y genera los .txt para WhatsApp.

Uso: doble clic o desde terminal:
    python enviar_facturas.py
"""

import io
import os
import re
import shutil
import sys

# UTF-8 en terminal Windows (solo al ejecutar directamente)
if __name__ == "__main__" or sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except AttributeError:
        pass

from pathlib import Path

import pdfplumber
import yagmail

try:
    import pyperclip
    PYPERCLIP_OK = True
except ImportError:
    PYPERCLIP_OK = False


# ============================================================
#  CONFIGURACION — se carga desde data/config.json
#  Copia config.example.json a data/config.json y completa tus datos
# ============================================================

import json as _json

_CONFIG_FILE = Path(__file__).parent / "data" / "config.json"
_EXAMPLE_FILE = Path(__file__).parent / "config.example.json"

def _cargar_config() -> dict:
    """Lee data/config.json. Si no existe, avisa y sale."""
    if not _CONFIG_FILE.exists():
        print(
            "\n  ERROR: No se encontró data/config.json\n"
            "  Copia 'config.example.json' como 'data/config.json'\n"
            "  y completa tus credenciales antes de ejecutar.\n"
        )
        input("Presiona Enter para salir...")
        sys.exit(1)
    with open(_CONFIG_FILE, encoding="utf-8") as f:
        return _json.load(f)

_cfg = _cargar_config()

MI_EMAIL    = _cfg.get("email", {}).get("address", "")
MI_PASSWORD = _cfg.get("email", {}).get("password", "")
MI_NOMBRE   = _cfg.get("remitente", {}).get("nombre", "Tu Nombre")
MI_EMPRESA  = _cfg.get("remitente", {}).get("empresa", "Tu Empresa")
MI_CARGO    = _cfg.get("remitente", {}).get("cargo", "Tu Cargo")
MI_TELEFONO = _cfg.get("whatsapp", {}).get("mi_telefono", "")

BANCO       = _cfg.get("banco", {}).get("nombre", "Tu Banco")
CTA_NOMBRE  = _cfg.get("banco", {}).get("titular", "Titular de la cuenta")
CTA_NUMERO  = _cfg.get("banco", {}).get("numero", "0000000")
CTA_TIPO    = _cfg.get("banco", {}).get("tipo", "Cta. Corriente")
CTA_CI      = _cfg.get("banco", {}).get("ci", "0000000000")

if not MI_EMAIL or not MI_PASSWORD:
    print(
        "\n  ERROR: Faltan las credenciales de correo en data/config.json\n"
        "  Completa 'email.address' y 'email.password'.\n"
    )
    input("Presiona Enter para salir...")
    sys.exit(1)

BASE          = Path(__file__).parent
CARPETA_POR_VENCER  = BASE / "por_vencer"
CARPETA_VENCIDAS    = BASE / "vencidas"
CARPETA_WHATSAPP    = BASE / "mensajes_whatsapp"
CARPETA_ENVIADAS    = BASE / "enviadas"

# ============================================================


def preparar_carpetas():
    for c in [CARPETA_POR_VENCER, CARPETA_VENCIDAS,
              CARPETA_WHATSAPP, CARPETA_ENVIADAS]:
        c.mkdir(exist_ok=True)


def limpiar(texto):
    lineas = [" ".join(l.split()) for l in texto.splitlines()]
    return "\n".join(lineas)


def extraer_datos(ruta_pdf: Path) -> dict:
    texto_bruto = ""
    with pdfplumber.open(ruta_pdf) as pdf:
        for pagina in pdf.pages:
            texto_bruto += (pagina.extract_text() or "") + "\n"

    texto  = limpiar(texto_bruto)
    lineas = texto.splitlines()

    datos = {
        "archivo":      ruta_pdf.name,
        "factura_no":   "",
        "fecha":        "",
        "razon_social": "",
        "telefono":     "",
        "emails":       [],
        "total":        "",
        "descripcion":  "",
    }

    m = re.search(r"FACTURA\s+No\.(\S+)", texto)
    if m:
        datos["factura_no"] = m.group(1)

    m = re.search(r"Fecha\s+Emisi.n:\s*(\d{2}/\d{2}/\d{4})", texto)
    if m:
        datos["fecha"] = m.group(1)

    m = re.search(r"Raz.n\s+Social:\s*(.+?)\s+RUC/CI:", texto)
    if m:
        nombre = m.group(1).strip()
        pos = next((i for i, l in enumerate(lineas)
                    if "Raz" in l and "Social" in l), None)
        if pos is not None and pos + 1 < len(lineas):
            sig = lineas[pos + 1].strip()
            if (sig and sig == sig.upper() and len(sig) <= 25
                    and not re.search(r"DIRECCI|FECHA|C.DIGO|RUC|TELEF", sig)):
                nombre += " " + sig
        datos["razon_social"] = nombre
    if not datos["razon_social"]:
        datos["razon_social"] = ruta_pdf.stem

    m = re.search(r"Direcci.n:.*?Tel.fono:\s*([\d\s]+)", texto)
    if m:
        datos["telefono"] = re.sub(r"\s+", "", m.group(1))[:15]

    idx_dir = next((i for i, l in enumerate(lineas)
                    if re.search(r"Direcci.n:", l)), None)
    if idx_dir is not None:
        email_texto = ""
        recolectando = False
        for linea in lineas[idx_dir:]:
            if "Correo:" in linea:
                recolectando = True
                email_texto += linea.split("Correo:", 1)[1]
                continue
            if recolectando:
                s = linea.strip()
                if re.search(r"C.digo|Informaci.n|Formas\s+de\s+pago|Subtotal", s):
                    break
                if len(s) > 60:
                    break
                email_texto += s
        email_sin_espacios = "".join(email_texto.split())
        encontrados = re.findall(r"[\w.\-+]+@[\w.\-]+\.\w{2,6}", email_sin_espacios)
        datos["emails"] = [e for e in encontrados
                           if "interbalanzas" not in e.lower() and e != MI_EMAIL]

    if not datos["emails"]:
        todos = re.findall(r"[\w.\-+]+@[\w.\-]+\.\w{2,6}", texto)
        datos["emails"] = [e for e in todos
                           if "interbalanzas" not in e.lower() and e != MI_EMAIL]

    m = re.search(r"Valor\s+Total:\s*\$?([\d.,]+)", texto)
    if m:
        datos["total"] = m.group(1)

    m = re.search(r"\d+\.\d{6}\s+([A-Z][A-Z0-9\s\-]+?)(?:\s+\d+\.\d|\s+\$)", texto)
    if m:
        datos["descripcion"] = m.group(1).strip()

    return datos


DATOS_BANCARIOS_EMAIL = (
    f"Para realizar el pago por transferencia:\n"
    f"   Banco   : {BANCO}\n"
    f"   Nombre  : {CTA_NOMBRE}\n"
    f"   {CTA_TIPO}: {CTA_NUMERO}\n"
    f"   C.I.    : {CTA_CI}\n"
)

DATOS_BANCARIOS_WA = (
    f"Para transferencia bancaria:\n"
    f"*{BANCO}*\n"
    f"{CTA_NOMBRE}\n"
    f"{CTA_TIPO}: *{CTA_NUMERO}*\n"
    f"C.I.: {CTA_CI}"
)

FIRMA_EMAIL = (
    f"\nSaludos cordiales,\n\n"
    f"{MI_NOMBRE}\n"
    f"{MI_EMPRESA} - {MI_CARGO}\n"
    f"Tel: {MI_TELEFONO} | Email: {MI_EMAIL}\n"
)

FIRMA_WA = (
    f"Saludos,\n"
    f"*{MI_NOMBRE}*\n"
    f"{MI_EMPRESA}\n"
    f"{MI_TELEFONO}"
)


def mensaje_email_por_vencer(d: dict) -> tuple:
    """Retorna (asunto, cuerpo) para factura por vencer."""
    desc = d["descripcion"] or "los productos/servicios adquiridos"
    asunto = f"Factura N° {d['factura_no']} - {MI_EMPRESA}"
    cuerpo = (
        f"Estimados senores {d['razon_social']},\n\n"
        f"Por medio del presente, nos permitimos hacer llegar la factura "
        f"N° {d['factura_no']} con fecha {d['fecha']}, "
        f"correspondiente a {desc}, por un valor de ${d['total']}.\n\n"
        f"Adjunto encontraran el comprobante electronico para su registro.\n\n"
        f"{DATOS_BANCARIOS_EMAIL}\n"
        f"Quedo a su entera disposicion para cualquier consulta o "
        f"confirmacion de recepcion.\n"
        f"{FIRMA_EMAIL}"
    )
    return asunto, cuerpo


def mensaje_email_vencida(d: dict) -> tuple:
    """Retorna (asunto, cuerpo) para factura vencida."""
    asunto = f"Recordatorio de pago - Factura N° {d['factura_no']} - {MI_EMPRESA}"
    cuerpo = (
        f"Estimados senores {d['razon_social']},\n\n"
        f"Esperamos que se encuentren bien. Nos permitimos recordarles "
        f"que la factura N° {d['factura_no']} con fecha {d['fecha']}, "
        f"por un valor de ${d['total']}, se encuentra pendiente de pago.\n\n"
        f"Les agradecemos gestionar el pago a la brevedad posible. "
        f"Para su comodidad, los datos bancarios son:\n\n"
        f"{DATOS_BANCARIOS_EMAIL}\n"
        f"Adjunto el comprobante para su referencia. Ante cualquier "
        f"inconveniente, quedamos a su disposicion.\n"
        f"{FIRMA_EMAIL}"
    )
    return asunto, cuerpo


def mensaje_whatsapp_por_vencer(d: dict) -> str:
    desc = d["descripcion"] or "nuestros productos/servicios"
    return (
        f"Estimados *{d['razon_social']}*,\n\n"
        f"Por este medio les hacemos llegar la factura "
        f"*N° {d['factura_no']}* con fecha {d['fecha']}, "
        f"correspondiente a _{desc}_, "
        f"por un valor de *${d['total']}*.\n\n"
        f"El comprobante fue enviado a su correo electronico registrado.\n\n"
        f"{DATOS_BANCARIOS_WA}\n\n"
        f"Quedo atento a cualquier consulta.\n\n"
        f"{FIRMA_WA}"
    )


def mensaje_whatsapp_vencida(d: dict) -> str:
    return (
        f"Estimados *{d['razon_social']}*,\n\n"
        f"Esperamos que se encuentren bien. Les recordamos que la factura "
        f"*N° {d['factura_no']}* con fecha {d['fecha']}, "
        f"por un valor de *${d['total']}*, "
        f"se encuentra pendiente de pago.\n\n"
        f"Les agradecemos gestionar el pago a la brevedad. "
        f"Pueden realizarlo mediante transferencia bancaria:\n\n"
        f"{DATOS_BANCARIOS_WA}\n\n"
        f"Adjunto el comprobante en su correo. Quedo atento a su "
        f"confirmacion de pago.\n\n"
        f"{FIRMA_WA}"
    )


def guardar_txt_whatsapp(nombre_cliente: str, mensaje: str):
    """Guarda el mensaje de WhatsApp como .txt."""
    nombre_archivo = re.sub(r'[\\/*?:"<>|]', "", nombre_cliente)[:60]
    ruta = CARPETA_WHATSAPP / f"{nombre_archivo}.txt"
    ruta.write_text(mensaje, encoding="utf-8")
    return ruta


def enviar_email(destinatarios: list, asunto: str, cuerpo: str, ruta_pdf: Path) -> bool:
    try:
        yag = yagmail.SMTP(MI_EMAIL, MI_PASSWORD)
        yag.send(
            to=destinatarios,
            subject=asunto,
            contents=cuerpo,
            attachments=str(ruta_pdf),
        )
        return True
    except Exception as e:
        print(f"  ERROR enviando email: {e}")
        return False


def procesar_carpeta(carpeta: Path, tipo: str):
    """
    tipo: 'por_vencer' o 'vencida'
    """
    pdfs = sorted(carpeta.glob("*.pdf"))
    if not pdfs:
        return 0

    print(f"\n{'='*58}")
    etiqueta = "POR VENCER" if tipo == "por_vencer" else "VENCIDAS - COBRO PENDIENTE"
    print(f"  [{etiqueta}]  {len(pdfs)} factura(s)")
    print(f"{'='*58}")

    procesadas = 0
    for ruta_pdf in pdfs:
        print(f"\n  Factura : {ruta_pdf.name}")
        print(f"  {'-'*54}")

        d = extraer_datos(ruta_pdf)
        print(f"  Cliente : {d['razon_social']}")
        print(f"  N°      : {d['factura_no']}   Fecha: {d['fecha']}   Total: ${d['total']}")
        print(f"  Email   : {', '.join(d['emails']) or 'No encontrado'}")
        print(f"  Tel     : {d['telefono'] or 'No encontrado'}")

        # Seleccionar mensajes segun tipo
        if tipo == "por_vencer":
            asunto, cuerpo = mensaje_email_por_vencer(d)
            texto_wa       = mensaje_whatsapp_por_vencer(d)
        else:
            asunto, cuerpo = mensaje_email_vencida(d)
            texto_wa       = mensaje_whatsapp_vencida(d)

        # Enviar email
        if d["emails"]:
            print(f"\n  Enviando email...")
            ok = enviar_email(d["emails"], asunto, cuerpo, ruta_pdf)
            if ok:
                print(f"  OK - Email enviado a {', '.join(d['emails'])}")
                destino = CARPETA_ENVIADAS / ruta_pdf.name
                shutil.move(str(ruta_pdf), destino)
                print(f"  OK - PDF movido a enviadas/")
            else:
                print(f"  FALLO - El PDF permanece en la carpeta")
        else:
            print(f"  AVISO - Sin email en la factura, no se envio correo.")

        # Guardar .txt para WhatsApp
        ruta_txt = guardar_txt_whatsapp(d["razon_social"], texto_wa)
        print(f"  OK - WhatsApp guardado: mensajes_whatsapp/{ruta_txt.name}")

        procesadas += 1

    return procesadas


def main():
    preparar_carpetas()

    print(f"\n{'='*58}")
    print(f"  COBRADOR - {MI_EMPRESA}")
    print(f"{'='*58}")

    total = 0
    total += procesar_carpeta(CARPETA_POR_VENCER, "por_vencer")
    total += procesar_carpeta(CARPETA_VENCIDAS,   "vencida")

    if total == 0:
        print("\n  No hay facturas en ninguna carpeta.")
        print("  Coloca los PDFs en 'por_vencer' o 'vencidas' y ejecuta de nuevo.")
    else:
        print(f"\n{'='*58}")
        print(f"  LISTO - {total} factura(s) procesada(s)")
        print(f"  Los mensajes de WhatsApp estan en: mensajes_whatsapp/")
        print(f"{'='*58}")

    input("\nPresiona Enter para salir...")


if __name__ == "__main__":
    main()
