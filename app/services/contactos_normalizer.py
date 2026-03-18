"""
app/services/contactos_normalizer.py — Normalizador universal de agendas de contactos

Carga cualquier XLS / XLSX / CSV que contenga una lista de contactos (clientes,
proveedores, agenda de teléfonos) y extrae: nombre, email, teléfono y RUC/CI.

Usa el mismo mecanismo de fuzzy matching de xls_normalizer pero con
sinónimos específicos para datos de contacto.

Uso:
    from app.services.contactos_normalizer import normalizar_contactos, importar_contactos_a_db

    resultado = normalizar_contactos("agenda_clientes.xlsx")
    resultado.contactos          # list[dict]
    resultado.software_detectado # "Contifico" | "Alegra" | "Genérico"

    n_nuevos, n_actualizados = importar_contactos_a_db(resultado.contactos)
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path


# ── Resultado ─────────────────────────────────────────────────────────────────

@dataclass
class ContactosResult:
    contactos:         list[dict]
    advertencias:      list[str]  = field(default_factory=list)
    software_detectado: str       = "Genérico"


# ── Sinónimos de columnas ──────────────────────────────────────────────────────

_SINONIMOS: dict[str, list[str]] = {
    "nombre": [
        "nombre", "razon social", "razón social", "cliente", "empresa",
        "name", "customer", "contacto", "beneficiario", "proveedor",
        "nombre cliente", "nombre empresa", "razon_social",
    ],
    "email": [
        "email", "correo", "e-mail", "mail",
        "correo electronico", "correo electrónico", "email cliente",
        "correo_electronico",
    ],
    "telefono": [
        "telefono", "teléfono", "cel", "celular", "phone",
        "movil", "móvil", "tel", "fono", "mobile", "whatsapp",
        "celular cliente", "telefono cliente", "contacto",
    ],
    "cedula_ruc": [
        "ruc", "cedula", "cédula", "identificacion", "identificación",
        "nif", "dni", "id fiscal", "tax id", "ci", "ci/ruc",
        "numero ruc", "número ruc",
    ],
}

_SCORE_MINIMO = 70   # más permisivo que xls_normalizer (columnas de contacto son más variadas)


# ── Punto de entrada público ───────────────────────────────────────────────────

def normalizar_contactos(ruta: str | Path) -> ContactosResult:
    """
    Carga cualquier archivo de contactos y retorna lista normalizada.
    Lanza ValueError o FileNotFoundError si el archivo es inválido.
    """
    ruta = Path(ruta)
    if not ruta.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {ruta}")

    ext = ruta.suffix.lower()
    if ext == ".csv":
        return _procesar_csv(ruta)
    elif ext in (".xls", ".xlsx"):
        return _procesar_xls(ruta)
    else:
        raise ValueError(
            f"Formato '{ext}' no soportado.\n"
            "Usa .xls, .xlsx o .csv exportado desde tu sistema de contactos."
        )


# ── Procesamiento XLS ──────────────────────────────────────────────────────────

def _procesar_xls(ruta: Path) -> ContactosResult:
    try:
        import xlrd
    except ImportError:
        raise ImportError("Instala xlrd==1.2.0: pip install xlrd==1.2.0")

    wb = xlrd.open_workbook(str(ruta))
    ws = wb.sheet_by_index(0)

    filas_muestra = [
        [_celda_str(ws, r, c) for c in range(ws.ncols)]
        for r in range(min(ws.nrows, 10))
    ]
    header_row_idx, headers = _encontrar_encabezado(filas_muestra)

    if header_row_idx is None:
        raise ValueError(
            "No se pudo detectar la fila de encabezado.\n"
            "Asegúrate de que la primera fila contenga los nombres de las columnas."
        )

    col_map = _mapear_columnas(headers)
    _validar_columnas_minimas(col_map, headers)

    contactos, advertencias = [], []
    for row_idx in range(header_row_idx + 1, ws.nrows):
        fila = [_celda_str(ws, row_idx, c) for c in range(ws.ncols)]
        if not any(v.strip() for v in fila):
            continue
        c, warn = _fila_a_contacto(fila, col_map)
        if c:
            contactos.append(c)
        elif warn:
            advertencias.append(warn)

    return ContactosResult(
        contactos=contactos,
        advertencias=advertencias,
        software_detectado=_inferir_software(headers),
    )


# ── Procesamiento CSV ──────────────────────────────────────────────────────────

def _procesar_csv(ruta: Path) -> ContactosResult:
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        filas = list(csv.reader(f))

    if not filas:
        raise ValueError("El archivo CSV está vacío.")

    header_row_idx, headers = _encontrar_encabezado(filas[:10])
    if header_row_idx is None:
        raise ValueError("No se pudo detectar la fila de encabezado.")

    col_map = _mapear_columnas(headers)
    _validar_columnas_minimas(col_map, headers)

    contactos, advertencias = [], []
    for fila in filas[header_row_idx + 1:]:
        if not any(v.strip() for v in fila):
            continue
        c, warn = _fila_a_contacto(fila, col_map)
        if c:
            contactos.append(c)
        elif warn:
            advertencias.append(warn)

    return ContactosResult(
        contactos=contactos,
        advertencias=advertencias,
        software_detectado=_inferir_software(headers),
    )


# ── Helpers internos ──────────────────────────────────────────────────────────

def _celda_str(ws, row: int, col: int) -> str:
    try:
        v = ws.cell_value(row, col)
        return "" if v is None else str(v).strip()
    except IndexError:
        return ""


def _encontrar_encabezado(filas: list[list[str]]) -> tuple[int | None, list[str]]:
    """Busca la primera fila con >= 2 celdas de texto (no números)."""
    for i, fila in enumerate(filas):
        textos = [v for v in fila if v and not _es_numero(v)]
        if len(textos) >= 2:
            return i, [str(h).strip() for h in fila]
    return None, []


def _es_numero(v) -> bool:
    try:
        float(str(v).replace(",", ".").replace("$", "").strip())
        return True
    except (ValueError, TypeError):
        return False


def _mapear_columnas(headers: list[str]) -> dict[str, int]:
    """Fuzzy matching: campo → índice de columna."""
    from rapidfuzz import fuzz

    headers_lower = [h.lower().strip() for h in headers]
    col_map: dict[str, int] = {}
    usados: set[int] = set()

    for campo, sinonimos in _SINONIMOS.items():
        mejor_score = 0
        mejor_idx   = -1
        for idx, header in enumerate(headers_lower):
            if idx in usados or not header:
                continue
            for sin in sinonimos:
                score = fuzz.ratio(header, sin.lower())
                if score > mejor_score:
                    mejor_score = score
                    mejor_idx   = idx
        if mejor_score >= _SCORE_MINIMO and mejor_idx >= 0:
            col_map[campo] = mejor_idx
            usados.add(mejor_idx)

    return col_map


def _validar_columnas_minimas(col_map: dict, headers: list[str]):
    if "nombre" not in col_map:
        raise ValueError(
            "No se encontró una columna de nombre o razón social.\n"
            f"Columnas detectadas: {[h for h in headers if h]}\n"
            "Renombra la columna del cliente a 'Nombre', 'Cliente' o 'Razón Social'."
        )


def _inferir_software(headers: list[str]) -> str:
    texto = " ".join(h.lower() for h in headers)
    if "alegra" in texto:
        return "Alegra"
    if "monica" in texto:
        return "Monica"
    if "contifico" in texto:
        return "Contifico"
    return "Genérico"


def _fila_a_contacto(fila: list[str], col_map: dict) -> tuple[dict | None, str]:
    def get(campo: str) -> str:
        idx = col_map.get(campo)
        if idx is None or idx >= len(fila):
            return ""
        return fila[idx].strip()

    nombre = get("nombre")
    if not nombre:
        return None, ""

    email      = get("email").lower()
    telefono   = get("telefono")
    cedula_ruc = get("cedula_ruc")

    if not email and not telefono:
        return None, f"Sin email ni teléfono para: {nombre}"

    return {
        "nombre":     nombre,
        "email":      email,
        "telefono":   telefono,
        "cedula_ruc": cedula_ruc,
    }, ""


# ── Importación a la base de datos ────────────────────────────────────────────

def importar_contactos_a_db(contactos: list[dict]) -> tuple[int, int]:
    """
    Hace upsert de cada contacto en la tabla contactos.
    Retorna (n_nuevos, n_actualizados).
    No sobreescribe datos manuales con confianza=1.0 si el nuevo tiene confianza menor.
    """
    from app import database as db

    n_nuevos       = 0
    n_actualizados = 0

    for c in contactos:
        nombre = c["nombre"]
        existente = db.get_contacto(nombre)

        if existente and existente.get("fuente") == "manual" and existente.get("confianza", 0) >= 1.0:
            # No sobreescribir datos manuales con importación masiva
            n_actualizados += 1
            continue

        db.upsert_contacto(
            nombre_contifico=nombre,
            email=c["email"] or None,
            telefono=c["telefono"] or None,
            fuente="xls_import",
            confianza=0.85,
        )

        if existente:
            n_actualizados += 1
        else:
            n_nuevos += 1

    return n_nuevos, n_actualizados
