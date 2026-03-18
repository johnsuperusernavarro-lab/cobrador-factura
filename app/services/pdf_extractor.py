"""
pdf_extractor.py — Extrae datos de facturas RIDE ecuatorianas (PDF)
Lógica extraída de enviar_facturas.py para reutilización en la GUI.
"""

import re
from pathlib import Path

def _get_mi_email() -> str:
    """Lee el email del remitente desde config.json para excluirlo del parsing."""
    try:
        from app.config_manager import ConfigManager
        return ConfigManager.get().get_email().get("address", "").lower()
    except Exception:
        return ""


def _limpiar(texto: str) -> str:
    lineas = [" ".join(l.split()) for l in texto.splitlines()]
    return "\n".join(lineas)


def extraer_datos(ruta_pdf: Path) -> dict:
    """
    Extrae los datos del cliente desde un RIDE ecuatoriano.

    Retorna dict con:
      archivo, factura_no, fecha, razon_social,
      telefono, emails (list), total, descripcion
    """
    try:
        import pdfplumber
    except ImportError:
        raise ImportError("Instala pdfplumber: pip install pdfplumber")

    texto_bruto = ""
    with pdfplumber.open(ruta_pdf) as pdf:
        for pagina in pdf.pages:
            texto_bruto += (pagina.extract_text() or "") + "\n"

    texto  = _limpiar(texto_bruto)
    lineas = texto.splitlines()

    datos = {
        "archivo":      ruta_pdf.name,
        "ruta":         str(ruta_pdf),
        "factura_no":   "",
        "fecha":        "",
        "razon_social": "",
        "telefono":     "",
        "emails":       [],
        "total":        "",
        "descripcion":  "",
    }

    # Número de factura
    m = re.search(r"FACTURA\s+No\.(\S+)", texto)
    if m:
        datos["factura_no"] = m.group(1)

    # Fecha de emisión
    m = re.search(r"Fecha\s+Emisi.n:\s*(\d{2}/\d{2}/\d{4})", texto)
    if m:
        datos["fecha"] = m.group(1)

    # Razón social del cliente (puede continuar en la línea siguiente)
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

    # Teléfono del cliente (junto a "Dirección:")
    m = re.search(r"Direcci.n:.*?Tel.fono:\s*([\d\s]+)", texto)
    if m:
        datos["telefono"] = re.sub(r"\s+", "", m.group(1))[:15]

    # Email del cliente (después de la sección "Dirección:" del cliente)
    idx_dir = next((i for i, l in enumerate(lineas)
                    if re.search(r"Direcci.n:", l)), None)
    if idx_dir is not None:
        email_texto  = ""
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
        sin_espacios = "".join(email_texto.split())
        encontrados  = re.findall(r"[\w.\-+]+@[\w.\-]+\.\w{2,6}", sin_espacios)
        mi_email = _get_mi_email()
        datos["emails"] = [e for e in encontrados
                           if e != mi_email]

    # Fallback: cualquier email que no sea el nuestro
    if not datos["emails"]:
        mi_email = _get_mi_email()
        todos = re.findall(r"[\w.\-+]+@[\w.\-]+\.\w{2,6}", texto)
        datos["emails"] = [e for e in todos
                           if e != mi_email]

    # Total
    m = re.search(r"Valor\s+Total:\s*\$?([\d.,]+)", texto)
    if m:
        datos["total"] = m.group(1)

    # Descripción (primer ítem de la factura)
    m = re.search(r"\d+\.\d{6}\s+([A-Z][A-Z0-9\s\-]+?)(?:\s+\d+\.\d|\s+\$)", texto)
    if m:
        datos["descripcion"] = m.group(1).strip()

    return datos
