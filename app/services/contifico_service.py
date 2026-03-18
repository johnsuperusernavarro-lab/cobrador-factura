"""
contifico_service.py — Cliente para la API REST de Contifico

Documentación:  https://api.contifico.com/sistema/api/v1/
Autenticación:  header  Authorization: <api_token>

Endpoints usados:
  GET /persona/          → lista de personas/clientes
  GET /documento/        → facturas (SIEMPRE filtrar por tipo_documento)
  GET /documento/{id}/   → documento individual

Campos confirmados con API real (2026-03):
  persona:    id, ruc, cedula, razon_social, telefonos, email, es_cliente
  documento:  id, documento, tipo_documento, estado, fecha_emision,
              fecha_vencimiento, total, saldo, descripcion, persona (embed),
              url_ride, url_xml, anulado
  Fecha:      formato DD/MM/YYYY
  Estado:     P = pendiente, A = anulado (otros valores posibles)
"""

import urllib.request
import urllib.error
import urllib.parse
import json
from datetime import date
from typing import Optional


BASE_URL = "https://api.contifico.com/sistema/api/v1"


class ContificoService:
    """Wrapper sobre la API REST de Contifico usando solo stdlib."""

    def __init__(self, api_token: str):
        self.api_token = api_token.strip()

    # ── HTTP base ────────────────────────────────────────────────────────────

    def _get(self, endpoint: str, params: Optional[dict] = None) -> dict | list:
        url = f"{BASE_URL}{endpoint}"
        if params:
            url += "?" + urllib.parse.urlencode(params)

        req = urllib.request.Request(url)
        req.add_header("Authorization", self.api_token)
        req.add_header("Accept", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:200]
            if e.code == 401:
                raise ContificoError("Token inválido o sin autorización (401)")
            if e.code == 403:
                raise ContificoError("Acceso denegado (403). Verifica los permisos del token.")
            raise ContificoError(f"Error HTTP {e.code}: {body}")
        except urllib.error.URLError as e:
            raise ContificoError(f"Sin conexión o URL incorrecta: {e.reason}")
        except Exception as e:
            raise ContificoError(str(e))

    # ── Verificación ─────────────────────────────────────────────────────────

    def verificar_conexion(self) -> tuple[bool, str]:
        """Prueba el token con una petición mínima."""
        try:
            data = self._get("/persona/", {"limit": 1})
            n = len(data) if isinstance(data, list) else data.get("count", "?")
            return True, f"Conexión exitosa — {n} contacto(s) disponibles"
        except ContificoError as e:
            return False, str(e)

    # ── Clientes / Personas ──────────────────────────────────────────────────

    def get_clientes(self, progreso_cb=None) -> list[dict]:
        """
        Devuelve todos los clientes de Contifico normalizados.
        Campos: razon_social, email, telefono, cedula_ruc.

        NOTA: La API devuelve lista plana (sin paginación) en una sola respuesta.
        """
        data = self._get("/persona/")

        # La API puede devolver lista directa o dict paginado
        if isinstance(data, list):
            items = data
        else:
            items = data.get("results", data.get("data", []))

        total = len(items)
        if progreso_cb:
            progreso_cb(0, total)

        clientes = []
        for i, raw in enumerate(items, 1):
            c = _normalizar_cliente(raw)
            if c["razon_social"]:
                clientes.append(c)
            if progreso_cb:
                progreso_cb(i, total)

        return clientes

    # ── Facturas / Documentos ────────────────────────────────────────────────

    def get_facturas_pendientes(self, progreso_cb=None) -> list[dict]:
        """
        Devuelve todas las facturas con saldo pendiente (estado=P, tipo=FAC).
        Cada item tiene el mismo formato que cobros_service.parse_reporte():
          cliente, factura_no, fecha_emision, fecha_vencimiento,
          descripcion, monto, monto_pendiente, tipo, email, telefono,
          url_ride, cedula_ruc.

        IMPORTANTE: siempre filtra por tipo_documento para evitar timeout.
        """
        todas = []
        limit = 200
        offset = 0

        while True:
            params = {
                "tipo_documento": "FAC",
                "estado":         "P",
                "limit":          limit,
                "offset":         offset,
            }
            data = self._get("/documento/", params)

            # Soporte lista directa o paginación
            if isinstance(data, list):
                batch = data
                hay_mas = False
            else:
                batch   = data.get("results", data.get("data", []))
                hay_mas = bool(data.get("next"))

            for raw in batch:
                if raw.get("anulado"):
                    continue
                doc = _normalizar_documento(raw)
                if doc and float(doc.get("monto_pendiente", 0)) > 0:
                    todas.append(doc)

            if progreso_cb:
                progreso_cb(len(todas), len(todas))  # total desconocido hasta el final

            if not hay_mas or len(batch) < limit:
                break
            offset += limit

        return todas

    def get_documento(self, doc_id: str) -> dict:
        """Devuelve un documento individual por su ID interno de Contifico."""
        raw = self._get(f"/documento/{doc_id}/")
        return _normalizar_documento(raw) or {}

    def get_cliente_por_ruc(self, ruc: str) -> dict | None:
        """Busca un cliente por RUC/cédula."""
        data = self._get("/persona/", {"ruc": ruc, "limit": 1})
        items = data if isinstance(data, list) else data.get("results", [])
        return _normalizar_cliente(items[0]) if items else None


# ── Normalización ─────────────────────────────────────────────────────────────

def _normalizar_cliente(raw: dict) -> dict:
    """
    Normaliza un objeto persona de la API al formato interno.
    Campo real de la API: 'telefonos' (no 'telefono').
    """
    nombre = (
        raw.get("razon_social") or raw.get("nombre") or raw.get("nombre_comercial") or ""
    ).strip()

    email = (
        raw.get("email") or raw.get("correo_1") or raw.get("correo") or ""
    ).strip().lower()
    if "," in email:
        email = email.split(",")[0].strip()

    # Campo real confirmado: 'telefonos'
    telefono = (
        raw.get("telefonos") or raw.get("telefono") or raw.get("celular") or ""
    ).strip()

    cedula = (
        raw.get("ruc") or raw.get("cedula_ruc") or raw.get("cedula") or ""
    ).strip()

    return {
        "razon_social": nombre,
        "email":        email,
        "telefono":     telefono,
        "cedula_ruc":   cedula,
    }


def _normalizar_documento(raw: dict) -> dict | None:
    """
    Convierte un documento de la API al formato interno de facturas
    (mismo que produce cobros_service.parse_reporte).
    """
    if not raw:
        return None

    persona = raw.get("persona") or {}
    cliente = (
        persona.get("razon_social") or persona.get("nombre_comercial") or ""
    ).strip()

    if not cliente:
        return None

    factura_no = raw.get("documento", "")
    fecha_emision    = _fecha_iso(raw.get("fecha_emision", ""))
    fecha_vencimiento = _fecha_iso(raw.get("fecha_vencimiento", ""))

    try:
        monto = float(raw.get("total", 0) or 0)
    except (ValueError, TypeError):
        monto = 0.0

    try:
        monto_pendiente = float(raw.get("saldo", 0) or 0)
    except (ValueError, TypeError):
        monto_pendiente = 0.0

    tipo = _calcular_tipo(fecha_vencimiento)

    email = (persona.get("email") or "").strip().lower()
    if "," in email:
        email = email.split(",")[0].strip()

    telefono = (
        persona.get("telefonos") or persona.get("telefono") or ""
    ).strip()

    cedula = (
        persona.get("ruc") or persona.get("cedula") or ""
    ).strip()

    return {
        "factura_no":        factura_no,
        "cliente":           cliente,
        "fecha_emision":     fecha_emision,
        "fecha_vencimiento": fecha_vencimiento,
        "descripcion":       raw.get("descripcion", ""),
        "monto":             monto,
        "monto_pendiente":   monto_pendiente,
        "tipo":              tipo,
        "email":             email,
        "telefono":          telefono,
        "cedula_ruc":        cedula,
        # Campos extra de Contifico (útiles para referencias)
        "url_ride":          raw.get("url_ride", ""),
        "contifico_id":      raw.get("id", ""),
    }


def _fecha_iso(fecha_str: str) -> str:
    """Convierte DD/MM/YYYY → YYYY-MM-DD. Retorna '' si no puede parsear."""
    if not fecha_str:
        return ""
    try:
        d, m, y = fecha_str.strip().split("/")
        return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    except Exception:
        return fecha_str  # devolver como está si no es el formato esperado


def _calcular_tipo(fecha_vencimiento_iso: str) -> str:
    """
    Determina si la factura está vencida o por vencer.
      vencida:    fecha_vencimiento < hoy
      por_vencer: fecha_vencimiento >= hoy
    """
    if not fecha_vencimiento_iso:
        return "vencida"
    try:
        fv = date.fromisoformat(fecha_vencimiento_iso)
        return "vencida" if fv < date.today() else "por_vencer"
    except Exception:
        return "vencida"


class ContificoError(Exception):
    pass
