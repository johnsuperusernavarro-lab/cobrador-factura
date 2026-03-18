"""
core/providers/excel_provider.py — Mapper universal de XLS/CSV.

Cualquier software contable puede ser soportado aquí mientras exporte a Excel.
La estructura del archivo se describe en un JSON en data/templates/.

Configuración esperada:
  {"type": "excel", "template": "alegra_xls"}

El template "contifico_xls" reutiliza el parser optimizado de cobros_service
en lugar de la lógica genérica, porque Contifico tiene un formato por grupos.

Formato del JSON de template (para archivos planos, una fila = una factura):
  {
    "software":      "Alegra",
    "sheet":         0,          // índice de la hoja
    "header_row":    0,          // fila del encabezado (0-based)
    "columns": {
      "cliente":           "Cliente",      // nombre de la columna en el encabezado
      "factura_no":        "Número",       // o índice numérico (0-based)
      "fecha_emision":     "Fecha",
      "fecha_vencimiento": "Vencimiento",
      "monto":             "Total",
      "monto_pendiente":   "Saldo",
      "descripcion":       "Descripción",
      "email":             "Email",        // opcional
      "telefono":          "Teléfono"      // opcional
    },
    "date_format":   "DD/MM/YYYY",         // para parsear fechas si es necesario
    "skip_if_zero":  true                  // omite filas con monto_pendiente = 0
  }
"""

import json
from datetime import date
from pathlib import Path

from core.base_provider import AccountingProvider, ProviderError

_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "data" / "templates"


class ExcelProvider(AccountingProvider):
    """
    Proveedor universal basado en archivos XLS/CSV.
    El archivo a cargar se pasa como 'file_path' en cfg, o se solicita al usuario.
    """

    def __init__(self, cfg: dict):
        self._template_name = cfg.get("template", "")
        self._file_path     = cfg.get("file_path", "")
        self._template      = self._cargar_template()

    @property
    def nombre(self) -> str:
        return self._template.get("software", "Excel/CSV")

    def _cargar_template(self) -> dict:
        if not self._template_name:
            return {}
        ruta = _TEMPLATES_DIR / f"{self._template_name}.json"
        if not ruta.exists():
            raise ProviderError(
                f"Template '{self._template_name}' no encontrado en {_TEMPLATES_DIR}.\n"
                f"Templates disponibles: {[f.stem for f in _TEMPLATES_DIR.glob('*.json')]}"
            )
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)

    def verificar_conexion(self) -> tuple[bool, str]:
        if self._file_path and Path(self._file_path).exists():
            return True, f"Archivo listo: {Path(self._file_path).name}"
        return False, "No se ha seleccionado ningún archivo XLS/CSV."

    def get_cartera(self, progreso_cb=None) -> list[dict]:
        if not self._file_path:
            raise ProviderError("Selecciona un archivo XLS/CSV primero.")

        ruta = Path(self._file_path)
        if not ruta.exists():
            raise ProviderError(f"Archivo no encontrado: {ruta}")

        # Usar el normalizador universal (detecta Contifico y cualquier otro)
        from app.services.xls_normalizer import normalizar_cartera
        try:
            resultado = normalizar_cartera(ruta, progreso_cb)
            return resultado.facturas
        except Exception as e:
            raise ProviderError(str(e)) from e

    def get_contactos(self, progreso_cb=None) -> list[dict]:
        """
        Para proveedores Excel, los contactos se extraen de la cartera.
        Solo devuelve filas que tienen email o teléfono.
        """
        facturas = self.get_cartera(progreso_cb)
        vistos   = set()
        contactos = []
        for f in facturas:
            nombre = f.get("cliente", "").strip()
            if not nombre or nombre in vistos:
                continue
            vistos.add(nombre)
            email = f.get("email", "")
            tel   = f.get("telefono", "")
            if email or tel:
                contactos.append({
                    "razon_social": nombre,
                    "email":        email,
                    "telefono":     tel,
                    "cedula_ruc":   f.get("cedula_ruc", ""),
                })
        return contactos

    # ── Parser genérico ───────────────────────────────────────────────────────

    def _parse_generico(self, ruta: Path, progreso_cb=None) -> list[dict]:
        ext = ruta.suffix.lower()
        if ext in (".xls", ".xlsx"):
            return self._parse_xls(ruta, progreso_cb)
        elif ext == ".csv":
            return self._parse_csv(ruta, progreso_cb)
        else:
            raise ProviderError(f"Formato no soportado: {ext}. Usa .xls, .xlsx o .csv")

    def _parse_xls(self, ruta: Path, progreso_cb=None) -> list[dict]:
        try:
            import xlrd
        except ImportError:
            raise ProviderError("Instala xlrd==1.2.0 para leer archivos .xls")

        wb = xlrd.open_workbook(str(ruta))
        ws = wb.sheet_by_index(self._template.get("sheet", 0))

        header_row = self._template.get("header_row", 0)
        headers    = [str(ws.cell_value(header_row, c)).strip()
                      for c in range(ws.ncols)]

        col_map = self._resolver_columnas(headers)
        facturas = []

        total = ws.nrows - header_row - 1
        for i, row_idx in enumerate(range(header_row + 1, ws.nrows)):
            row = [ws.cell_value(row_idx, c) for c in range(ws.ncols)]
            if not any(str(v).strip() for v in row):
                continue
            f = self._fila_a_factura(row, col_map)
            if f:
                facturas.append(f)
            if progreso_cb:
                progreso_cb(i + 1, total)

        return facturas

    def _parse_csv(self, ruta: Path, progreso_cb=None) -> list[dict]:
        import csv
        with open(ruta, encoding="utf-8-sig", newline="") as f:
            reader = list(csv.reader(f))

        if not reader:
            return []

        header_row = self._template.get("header_row", 0)
        headers    = [h.strip() for h in reader[header_row]]
        col_map    = self._resolver_columnas(headers)
        facturas   = []

        total = len(reader) - header_row - 1
        for i, row in enumerate(reader[header_row + 1:]):
            if not any(v.strip() for v in row):
                continue
            f = self._fila_a_factura(row, col_map)
            if f:
                facturas.append(f)
            if progreso_cb:
                progreso_cb(i + 1, total)

        return facturas

    def _resolver_columnas(self, headers: list[str]) -> dict[str, int]:
        """
        Convierte el mapa de columnas del template a índices enteros.
        Acepta nombre de columna (str) o índice numérico directamente.
        """
        mapping = self._template.get("columns", {})
        result  = {}
        for field, col_ref in mapping.items():
            if isinstance(col_ref, int):
                result[field] = col_ref
            else:
                # Buscar por nombre de columna (case-insensitive)
                ref_lower = str(col_ref).lower()
                for idx, h in enumerate(headers):
                    if h.lower() == ref_lower:
                        result[field] = idx
                        break
        return result

    def _fila_a_factura(self, row: list, col_map: dict) -> dict | None:
        def get(field, default=""):
            idx = col_map.get(field)
            if idx is None or idx >= len(row):
                return default
            val = row[idx]
            return str(val).strip() if val is not None else default

        def get_float(field) -> float:
            try:
                return float(str(get(field, "0")).replace(",", ".").replace("$", "").strip() or 0)
            except (ValueError, TypeError):
                return 0.0

        cliente        = get("cliente")
        factura_no     = get("factura_no")
        monto_pend     = get_float("monto_pendiente")

        if not cliente:
            return None
        if self._template.get("skip_if_zero", True) and monto_pend == 0:
            return None

        fecha_venc = get("fecha_vencimiento")
        tipo       = _calcular_tipo(fecha_venc)

        return {
            "cliente":           cliente,
            "factura_no":        factura_no,
            "fecha_emision":     get("fecha_emision"),
            "fecha_vencimiento": fecha_venc,
            "descripcion":       get("descripcion"),
            "monto":             get_float("monto"),
            "monto_pendiente":   round(monto_pend, 2),
            "tipo":              tipo,
            "email":             get("email"),
            "telefono":          get("telefono"),
            "cedula_ruc":        get("cedula_ruc"),
        }


def _calcular_tipo(fecha_str: str) -> str:
    if not fecha_str:
        return "vencida"
    # Normalizar DD/MM/YYYY → YYYY-MM-DD
    try:
        if "/" in fecha_str:
            d, m, y = fecha_str.strip().split("/")
            fecha_str = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
        fv = date.fromisoformat(fecha_str)
        return "vencida" if fv < date.today() else "por_vencer"
    except Exception:
        return "vencida"
