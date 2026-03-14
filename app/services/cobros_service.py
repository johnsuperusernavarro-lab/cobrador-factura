"""
cobros_service.py — Parsea el reporte CarteraPorCobrar.xls de Contifico

Retorna lista de facturas con:
  cliente, factura_no, fecha_emision, fecha_vencimiento,
  descripcion, monto, tipo ('por_vencer' | 'vencida')
"""

from pathlib import Path


def _to_float(val) -> float:
    """Convierte celda XLS a float; retorna 0.0 si vacío o inválido."""
    if val is None:
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def _fmt_fecha(val) -> str:
    """Convierte fecha XLS (string 'DD/MM/YYYY' o número serial) a string legible."""
    if not val:
        return ""
    s = str(val).strip()
    if "/" in s or "-" in s:
        return s
    # Número serial de Excel → fecha
    try:
        import datetime
        n = int(float(s))
        base = datetime.date(1899, 12, 30)
        d = base + datetime.timedelta(days=n)
        return d.strftime("%d/%m/%Y")
    except Exception:
        return s


def parse_reporte(ruta_xls: str | Path) -> list[dict]:
    """
    Lee el .xls de Contifico y retorna lista de dicts con datos de facturas.

    Estructura real del XLS de Contifico (CarteraPorCobrar):
    - Col 0:  Cliente (código/nombre)
    - Col 1:  Razón Social
    - Col 2:  Tipo Documento ("FAC")
    - Col 3:  # Documento
    - Col 4:  F. Emisión
    - Col 5:  F. Vencimiento
    - Col 6:  Vendedor
    - Col 7:  Centro de Costo
    - Col 8:  Categoría de Persona
    - Col 9:  Por vencer
    - Col 10: 30 días vencido
    - Col 11: 60 días vencido
    - Col 12: 90 días vencido
    - Col 13: 120 días vencido
    - Col 14: > 120 días vencido
    - Col 15: Total
    - Col 16: Descripción
    - Col 17: Valor documento
    - Col 18: Retenciones
    - Col 19: Cobros
    """
    try:
        import xlrd
    except ImportError:
        raise ImportError(
            "Instala xlrd: pip install xlrd==1.2.0\n"
            "(xlrd 2.x ya no soporta .xls; usa la versión 1.2.0)"
        )

    ruta = Path(ruta_xls)
    if not ruta.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {ruta}")

    wb = xlrd.open_workbook(str(ruta))
    ws = wb.sheet_by_index(0)

    facturas: list[dict] = []
    cliente_actual = ""

    for row_idx in range(ws.nrows):
        row = [ws.cell_value(row_idx, c) for c in range(ws.ncols)]

        # Detectar fila de encabezado o fila vacía
        if not any(str(v).strip() for v in row):
            continue

        col0 = str(row[0]).strip() if len(row) > 0 else ""
        col1 = str(row[1]).strip() if len(row) > 1 else ""
        col2 = str(row[2]).strip().upper() if len(row) > 2 else ""

        # Fila resumen de cliente (col 0 tiene código, col 2 vacía o no es FAC)
        if col0 and col2 != "FAC":
            cliente_actual = col1 or col0
            continue

        # Fila de detalle con factura
        if col2 == "FAC":
            if col1:
                cliente_actual = col1

            factura_no    = str(row[3]).strip() if len(row) > 3 else ""
            fecha_emision = _fmt_fecha(row[4]) if len(row) > 4 else ""
            fecha_venc    = _fmt_fecha(row[5]) if len(row) > 5 else ""
            descripcion   = str(row[16]).strip() if len(row) > 16 else ""
            monto         = _to_float(row[15]) if len(row) > 15 else 0.0

            # Clasificar por estado de vencimiento
            # Col 9 = Por vencer; cols 10-14 = buckets vencidos
            por_vencer = _to_float(row[9]) if len(row) > 9 else 0.0
            vencido_cols = [_to_float(row[c]) for c in range(10, min(15, len(row)))]
            total_vencido = sum(vencido_cols)

            if total_vencido > 0:
                tipo = "vencida"
                monto_pendiente = total_vencido
            elif por_vencer > 0:
                tipo = "por_vencer"
                monto_pendiente = por_vencer
            else:
                # Sin saldo pendiente → omitir
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
            })

    return facturas


def agrupar_por_cliente(facturas: list[dict]) -> dict[str, list[dict]]:
    """Agrupa lista de facturas por nombre de cliente."""
    grupos: dict[str, list[dict]] = {}
    for f in facturas:
        grupos.setdefault(f["cliente"], []).append(f)
    return grupos


def totales(facturas: list[dict]) -> dict:
    """Calcula totales generales."""
    vencidas   = [f for f in facturas if f["tipo"] == "vencida"]
    por_vencer = [f for f in facturas if f["tipo"] == "por_vencer"]
    return {
        "total_vencido":    round(sum(f["monto_pendiente"] for f in vencidas), 2),
        "total_por_vencer": round(sum(f["monto_pendiente"] for f in por_vencer), 2),
        "n_vencidas":       len(vencidas),
        "n_por_vencer":     len(por_vencer),
        "n_total":          len(facturas),
    }
