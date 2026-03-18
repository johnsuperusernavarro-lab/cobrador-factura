"""
app/services/xls_normalizer.py — Normalizador universal de Cartera por Cobrar

Carga cualquier archivo XLS / XLSX / CSV y retorna facturas en el formato
interno estándar, independientemente del software de origen.

Formatos soportados de forma transparente:
  ✓ Contifico / Siigo Ecuador   (auto-detectado por estructura de buckets)
  ✓ Alegra                      (headers en español o inglés)
  ✓ Monica 11                   (formato plano)
  ✓ Dora.ec                     (formato plano)
  ✓ Cualquier XLS/XLSX/CSV      (mapeo automático por nombre de columna)

Retorna siempre el mismo formato:
  {
    "cliente":           str,
    "factura_no":        str,
    "fecha_emision":     str,   # DD/MM/YYYY
    "fecha_vencimiento": str,   # DD/MM/YYYY
    "descripcion":       str,
    "monto":             float,
    "monto_pendiente":   float,
    "tipo":              str,   # "vencida" | "por_vencer"
    "email":             str,
    "telefono":          str,
    "cedula_ruc":        str,
    "_fuente":           str,   # nombre del software detectado
  }

Uso:
    from app.services.xls_normalizer import normalizar_cartera, DetectionResult
    result = normalizar_cartera("CarteraPorCobrar.xls")
    print(result.software)        # "Contifico"
    print(len(result.facturas))   # 143
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable


# ── Resultado del normalizador ─────────────────────────────────────────────────

@dataclass
class DetectionResult:
    software:     str             # nombre del software detectado
    facturas:     list[dict]      # lista normalizada
    advertencias: list[str] = field(default_factory=list)   # filas omitidas/problemas
    col_map:      dict = field(default_factory=dict)         # campo → índice de columna
    col_scores:   dict = field(default_factory=dict)         # campo → mejor score fuzzy (0-100)
    headers:      list = field(default_factory=list)         # headers originales del archivo


# ── Sinónimos de columnas (fuzzy matching) ─────────────────────────────────────

_SINONIMOS: dict[str, list[str]] = {
    "cliente": [
        "cliente", "razon social", "razón social", "nombre", "nombre cliente",
        "cliente proveedor", "empresa", "name", "customer",
    ],
    "factura_no": [
        "factura", "número", "numero", "nro", "comprobante", "documento",
        "número documento", "numero factura", "invoice", "doc", "voucher",
        "número comprobante", "num doc",
    ],
    "fecha_emision": [
        "fecha emision", "fecha emisión", "f emision", "f. emision",
        "fecha", "date", "fecha doc", "issue date", "fecha documento",
    ],
    "fecha_vencimiento": [
        "vencimiento", "fecha vencimiento", "fecha venc", "vence",
        "due date", "fecha de vencimiento", "f. vencimiento", "f venc",
        "fecha limite", "fecha límite",
    ],
    "monto": [
        "total", "valor", "monto", "importe", "amount", "valor total",
        "total factura", "valor documento", "gross",
    ],
    "monto_pendiente": [
        "saldo", "pendiente", "saldo pendiente", "balance", "debe",
        "adeuda", "por cobrar", "saldo deudor", "outstanding", "amount due",
        "saldo factura", "valor pendiente", "por pagar",
    ],
    "descripcion": [
        "descripcion", "descripción", "detalle", "concepto", "description",
        "item", "producto", "servicio", "glosa",
    ],
    "email": [
        "email", "correo", "e-mail", "mail", "correo electronico",
        "correo electrónico", "email cliente",
    ],
    "telefono": [
        "telefono", "teléfono", "cel", "celular", "phone", "movil",
        "móvil", "tel", "fono", "mobile",
    ],
    "cedula_ruc": [
        "ruc", "cedula", "cédula", "identificacion", "identificación",
        "nif", "dni", "id fiscal", "tax id", "ci", "ci/ruc",
    ],
}


# ── Punto de entrada público ───────────────────────────────────────────────────

def normalizar_cartera(
    ruta: str | Path,
    progreso_cb: Callable[[int, int], None] | None = None,
) -> DetectionResult:
    """
    Carga cualquier archivo de cartera y retorna facturas normalizadas.
    Auto-detecta el formato; nunca falla silenciosamente (lanza ValueError).
    """
    ruta = Path(ruta)
    if not ruta.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {ruta}")

    ext = ruta.suffix.lower()

    if ext == ".csv":
        return _procesar_csv(ruta, progreso_cb)
    elif ext in (".xls", ".xlsx"):
        return _procesar_xls(ruta, progreso_cb)
    else:
        raise ValueError(
            f"Formato '{ext}' no soportado.\n"
            "Usa .xls, .xlsx o .csv exportado desde tu software contable."
        )


# ── Procesamiento XLS / XLSX ───────────────────────────────────────────────────

def _procesar_xls(ruta: Path, progreso_cb=None) -> DetectionResult:
    try:
        import xlrd
    except ImportError:
        raise ImportError("Instala xlrd==1.2.0:  pip install xlrd==1.2.0")

    wb = xlrd.open_workbook(str(ruta))
    ws = wb.sheet_by_index(0)

    # ── Detectar formato ──────────────────────────────────────────────────
    if _es_formato_contifico(ws):
        return _parse_contifico(ws, progreso_cb)

    # Formato plano: buscar fila de encabezado
    header_row, headers = _encontrar_encabezado_xls(ws)
    if header_row is None:
        raise ValueError(
            "No se pudo detectar el encabezado del archivo.\n"
            "Asegúrate de que la primera fila visible contenga los nombres de las columnas."
        )

    col_map, col_scores = _mapear_columnas(headers)
    _validar_columnas_minimas(col_map, headers)

    software = _inferir_software(headers)
    advertencias = []
    facturas = []
    total = ws.nrows - header_row - 1

    for i, row_idx in enumerate(range(header_row + 1, ws.nrows)):
        fila = [_celda_str(ws, row_idx, c) for c in range(ws.ncols)]
        if not any(v.strip() for v in fila):
            continue
        f, warn = _fila_a_factura(fila, col_map, software)
        if f:
            facturas.append(f)
        elif warn:
            advertencias.append(warn)
        if progreso_cb:
            progreso_cb(i + 1, total)

    return DetectionResult(software=software, facturas=facturas,
                           advertencias=advertencias, col_map=col_map,
                           col_scores=col_scores, headers=headers)


def _celda_str(ws, row: int, col: int) -> str:
    try:
        v = ws.cell_value(row, col)
        return "" if v is None else str(v).strip()
    except IndexError:
        return ""


# ── Procesamiento CSV ──────────────────────────────────────────────────────────

def _procesar_csv(ruta: Path, progreso_cb=None) -> DetectionResult:
    filas = None
    for encoding in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            with open(ruta, encoding=encoding, newline="") as f:
                filas = list(csv.reader(f))
            break
        except (UnicodeDecodeError, LookupError):
            continue

    if filas is None:
        raise ValueError(
            "No se pudo leer el CSV. Guárdalo como UTF-8 desde tu software contable."
        )

    if not filas:
        raise ValueError("El archivo CSV está vacío.")

    # Buscar fila de encabezado (>= 3 celdas de texto, igual que XLS)
    header_row = None
    for i, fila in enumerate(filas[:10]):
        celdas_texto = [c.strip() for c in fila if c.strip() and not _es_numero(c.strip())]
        if len(celdas_texto) >= 3:
            header_row = i
            break

    if header_row is None:
        raise ValueError(
            "No se pudo detectar el encabezado del CSV.\n"
            "Asegúrate de que la primera fila contenga los nombres de las columnas."
        )

    headers = [h.strip() for h in filas[header_row]]
    col_map, col_scores = _mapear_columnas(headers)
    _validar_columnas_minimas(col_map, headers)

    software = _inferir_software(headers)
    advertencias = []
    facturas = []
    total = len(filas) - header_row - 1

    for i, fila in enumerate(filas[header_row + 1:]):
        if not any(v.strip() for v in fila):
            continue
        f, warn = _fila_a_factura(fila, col_map, software)
        if f:
            facturas.append(f)
        elif warn:
            advertencias.append(warn)
        if progreso_cb:
            progreso_cb(i + 1, total)

    return DetectionResult(software=software, facturas=facturas,
                           advertencias=advertencias, col_map=col_map,
                           col_scores=col_scores, headers=headers)


# ── Detección formato Contifico ────────────────────────────────────────────────

def _es_formato_contifico(ws) -> bool:
    """
    Contifico tiene un formato por grupos donde las filas de detalle tienen
    "FAC" en la columna 2. Si encontramos al menos 2 de esas filas es Contifico.
    """
    conteo = 0
    for row_idx in range(min(ws.nrows, 50)):
        try:
            val = str(ws.cell_value(row_idx, 2)).strip().upper()
            if val == "FAC":
                conteo += 1
                if conteo >= 2:
                    return True
        except IndexError:
            pass
    return False


def _parse_contifico(ws, progreso_cb=None) -> DetectionResult:
    """Parser especializado para el XLS de Contifico (buckets de antigüedad)."""
    facturas = []
    cliente_actual = ""
    advertencias = []
    total = ws.nrows

    for row_idx in range(ws.nrows):
        row = [_celda_str(ws, row_idx, c) for c in range(ws.ncols)]
        if not any(v.strip() for v in row):
            continue

        col0 = row[0] if len(row) > 0 else ""
        col1 = row[1] if len(row) > 1 else ""
        col2 = row[2].upper() if len(row) > 2 else ""

        # Fila de agrupación de cliente
        if col0 and col2 != "FAC":
            cliente_actual = col1 or col0
            continue

        if col2 != "FAC":
            continue

        if col1:
            cliente_actual = col1

        factura_no      = row[3]  if len(row) > 3  else ""
        fecha_emision   = _fmt_fecha(row[4]  if len(row) > 4  else "")
        fecha_venc      = _fmt_fecha(row[5]  if len(row) > 5  else "")
        descripcion     = row[16] if len(row) > 16 else ""
        monto           = _to_float(row[15] if len(row) > 15 else 0)

        por_vencer    = _to_float(row[9]  if len(row) > 9  else 0)
        vencido_total = sum(_to_float(row[c]) for c in range(10, min(15, len(row))))

        if vencido_total > 0:
            tipo = "vencida"
            monto_pendiente = vencido_total
        elif por_vencer > 0:
            tipo = "por_vencer"
            monto_pendiente = por_vencer
        else:
            continue  # sin saldo pendiente

        if not cliente_actual:
            continue

        facturas.append({
            "cliente":           cliente_actual,
            "factura_no":        factura_no,
            "fecha_emision":     fecha_emision,
            "fecha_vencimiento": fecha_venc,
            "descripcion":       descripcion,
            "monto":             monto,
            "monto_pendiente":   round(monto_pendiente, 2),
            "tipo":              tipo,
            "email":             "",
            "telefono":          "",
            "cedula_ruc":        "",
            "_fuente":           "Contifico",
        })

        if progreso_cb:
            progreso_cb(row_idx, total)

    return DetectionResult(software="Contifico", facturas=facturas,
                           advertencias=advertencias)


# ── Detección automática de columnas ──────────────────────────────────────────

def _encontrar_encabezado_xls(ws) -> tuple[int | None, list[str]]:
    """
    Busca la primera fila que parezca un encabezado (>= 3 celdas no vacías
    con texto, no números). Prueba las primeras 10 filas.
    """
    for row_idx in range(min(ws.nrows, 10)):
        fila = [_celda_str(ws, row_idx, c) for c in range(ws.ncols)]
        celdas_texto = [v for v in fila if v and not _es_numero(v)]
        if len(celdas_texto) >= 3:
            return row_idx, fila
    return None, []


def _es_numero(v: str) -> bool:
    try:
        float(v.replace(",", ".").replace("$", "").strip())
        return True
    except ValueError:
        return False


def _mapear_columnas(headers: list[str]) -> tuple[dict[str, int], dict[str, int]]:
    """
    Mapea nombre de campo → índice de columna usando fuzzy matching.
    Usa un score mínimo de 72.
    Retorna (col_map, col_scores) donde col_scores registra el mejor score
    de cada campo (incluyendo los no mapeados, para mostrar al usuario).
    """
    from rapidfuzz import fuzz

    headers_lower = [h.lower().strip() for h in headers]
    col_map:    dict[str, int] = {}
    col_scores: dict[str, int] = {}  # campo → mejor score (0-100), siempre presente
    usados: set[int] = set()

    prioridad = ["cliente", "factura_no", "monto_pendiente", "monto",
                 "fecha_vencimiento", "fecha_emision",
                 "descripcion", "email", "telefono", "cedula_ruc"]

    for campo in prioridad:
        sinonimos = _SINONIMOS.get(campo, [campo])
        mejor_score = 0
        mejor_idx   = -1

        for idx, header in enumerate(headers_lower):
            if idx in usados or not header:
                continue
            for sin in sinonimos:
                score = max(
                    fuzz.ratio(header, sin.lower()),
                    fuzz.partial_ratio(header, sin.lower()),
                )
                if score > mejor_score:
                    mejor_score = score
                    mejor_idx   = idx

        col_scores[campo] = mejor_score   # guardar siempre, incluso si no alcanza umbral

        if mejor_score >= 72 and mejor_idx >= 0:
            col_map[campo] = mejor_idx
            usados.add(mejor_idx)

    return col_map, col_scores


def _validar_columnas_minimas(col_map: dict, headers: list[str]):
    """Lanza ValueError si no hay al menos cliente y monto/monto_pendiente."""
    if "cliente" not in col_map:
        raise ValueError(
            "No se encontró una columna de cliente en el archivo.\n"
            f"Columnas detectadas: {[h for h in headers if h]}\n"
            "Renombra la columna del cliente a 'Cliente' o 'Razón Social'."
        )
    if "monto_pendiente" not in col_map and "monto" not in col_map:
        raise ValueError(
            "No se encontró una columna de monto o saldo pendiente.\n"
            f"Columnas detectadas: {[h for h in headers if h]}\n"
            "Renombra la columna de saldo a 'Saldo' o 'Monto Pendiente'."
        )


def _inferir_software(headers: list[str]) -> str:
    """Intenta identificar el software por patrones en los headers."""
    texto = " ".join(h.lower() for h in headers)
    if "alegra" in texto:
        return "Alegra"
    if "monica" in texto or "comprobante" in texto:
        return "Monica"
    if "dora" in texto:
        return "Dora"
    if "quickbooks" in texto or "quickbook" in texto:
        return "QuickBooks"
    # Si tiene la columna "saldo" y "vencimiento" es probablemente ecuatoriano
    if "saldo" in texto and "vencimiento" in texto:
        return "Genérico EC"
    return "Genérico"


# ── Conversión de fila → factura ───────────────────────────────────────────────

def _fila_a_factura(fila: list[str], col_map: dict, software: str) -> tuple[dict | None, str]:
    """
    Convierte una fila del XLS al formato interno.
    Retorna (factura, "") si OK, o (None, mensaje_error) si se omite.
    """
    def get(campo: str, default: str = "") -> str:
        idx = col_map.get(campo)
        if idx is None or idx >= len(fila):
            return default
        return fila[idx].strip()

    def get_float(campo: str) -> float:
        return _to_float(get(campo, "0"))

    cliente = get("cliente")
    if not cliente:
        # Solo advertir si la fila tiene otros datos (no es una fila realmente vacía)
        if get("factura_no") or get("monto_pendiente") or get("monto"):
            return None, "Fila omitida: sin nombre de cliente"
        return None, ""

    # Monto pendiente: preferir columna específica, si no usar monto total
    monto_pend = get_float("monto_pendiente")
    monto      = get_float("monto") or monto_pend
    if monto_pend == 0:
        monto_pend = monto

    # Omitir si no hay saldo
    if monto_pend <= 0:
        return None, ""

    fecha_venc  = _fmt_fecha(get("fecha_vencimiento"))
    fecha_emis  = _fmt_fecha(get("fecha_emision"))
    tipo        = _calcular_tipo(fecha_venc)

    return {
        "cliente":           cliente,
        "factura_no":        get("factura_no"),
        "fecha_emision":     fecha_emis,
        "fecha_vencimiento": fecha_venc,
        "descripcion":       get("descripcion"),
        "monto":             round(monto, 2),
        "monto_pendiente":   round(monto_pend, 2),
        "tipo":              tipo,
        "email":             get("email").lower(),
        "telefono":          get("telefono"),
        "cedula_ruc":        get("cedula_ruc"),
        "_fuente":           software,
    }, ""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_float(val) -> float:
    if val is None:
        return 0.0
    s = str(val).replace("$", "").replace(" ", "").strip()
    if not s:
        return 0.0
    try:
        if "," in s and "." in s:
            # Determinar cuál es el separador decimal por posición
            if s.rindex(",") > s.rindex("."):
                # Formato europeo: "1.234,56" → punto=miles, coma=decimal
                s = s.replace(".", "").replace(",", ".")
            else:
                # Formato anglosajón: "1,234.56" → coma=miles, punto=decimal
                s = s.replace(",", "")
        elif "," in s:
            # Solo coma: tratar como separador decimal
            s = s.replace(",", ".")
        return float(s or 0)
    except (ValueError, TypeError):
        return 0.0


def _fmt_fecha(val) -> str:
    """Normaliza fechas de múltiples formatos a DD/MM/YYYY."""
    if not val:
        return ""
    s = str(val).strip()

    # YYYY-MM-DD → DD/MM/YYYY (ISO con guiones — detectar primero)
    if "-" in s and len(s) >= 10:
        try:
            y, m, d = s[:10].split("-")
            if len(y) == 4 and y.isdigit():
                return f"{d.zfill(2)}/{m.zfill(2)}/{y}"
        except Exception:
            pass

    # Formatos con barra
    if "/" in s and len(s) == 10:
        parts = s.split("/")
        if len(parts) == 3:
            a, b, c = parts
            # DD/MM/YYYY: primer segmento <= 31 y último es año de 4 dígitos
            if len(c) == 4 and c.isdigit() and a.isdigit() and int(a) <= 31:
                return s
            # YYYY/MM/DD: primer segmento es año de 4 dígitos → convertir
            if len(a) == 4 and a.isdigit():
                return f"{c.zfill(2)}/{b.zfill(2)}/{a}"

    # Número serial de Excel → fecha
    if s.replace(".", "").isdigit():
        try:
            import datetime
            n    = int(float(s))
            base = datetime.date(1899, 12, 30)
            d    = base + datetime.timedelta(days=n)
            return d.strftime("%d/%m/%Y")
        except Exception:
            pass

    return s


def _calcular_tipo(fecha_str: str) -> str:
    """DD/MM/YYYY → 'vencida' o 'por_vencer'."""
    if not fecha_str:
        return "por_vencer"   # sin fecha: no penalizar al cliente por defecto
    try:
        d, m, y = fecha_str.split("/")
        fv = date(int(y), int(m), int(d))
        return "vencida" if fv < date.today() else "por_vencer"
    except Exception:
        return "por_vencer"   # fecha no parseable: no penalizar
