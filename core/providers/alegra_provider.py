"""
core/providers/alegra_provider.py — Adaptador Alegra.

Estado: MOCK — estructura lista, URL y auth confirmadas con la documentación
pública de Alegra (developer.alegra.com). Cuando tengas un cliente con Alegra:
  1. Pon su email y token en los ajustes
  2. Cambia MOCK_MODE = False
  3. Listo — el cableado ya está hecho.

API Alegra:
  Base:  https://app.alegra.com/api/v1
  Auth:  Basic Auth  (email + api_token como password)
  Docs:  https://developer.alegra.com

Configuración esperada:
  {"type": "alegra", "email": "usuario@empresa.com", "token": "<api_token>"}
"""

import json
import urllib.request
import urllib.error
import base64
from datetime import date

from core.base_provider import AccountingProvider, ProviderError

MOCK_MODE = True   # ← cambiar a False cuando tengas credenciales reales

_BASE = "https://app.alegra.com/api/v1"


class AlegraProvider(AccountingProvider):

    def __init__(self, cfg: dict):
        self._email = cfg.get("email", "")
        self._token = cfg.get("token", "")
        if not MOCK_MODE and (not self._email or not self._token):
            raise ProviderError("Alegra requiere 'email' y 'token' en la configuración.")

    @property
    def nombre(self) -> str:
        return "Alegra"

    # ── HTTP ──────────────────────────────────────────────────────────────────

    def _auth_header(self) -> str:
        credenciales = f"{self._email}:{self._token}"
        encoded = base64.b64encode(credenciales.encode()).decode()
        return f"Basic {encoded}"

    def _get(self, endpoint: str, params: dict | None = None) -> dict | list:
        url = f"{_BASE}{endpoint}"
        if params:
            import urllib.parse
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url)
        req.add_header("Authorization", self._auth_header())
        req.add_header("Accept", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:200]
            if e.code == 401:
                raise ProviderError("Token Alegra inválido (401). Verifica email y token.")
            raise ProviderError(f"Alegra HTTP {e.code}: {body}")
        except urllib.error.URLError as e:
            raise ProviderError(f"Sin conexión con Alegra: {e.reason}")

    # ── Interfaz AccountingProvider ───────────────────────────────────────────

    def verificar_conexion(self) -> tuple[bool, str]:
        if MOCK_MODE:
            return True, "Alegra MOCK — modo demostración (sin credenciales reales)"
        try:
            data = self._get("/company")
            nombre = data.get("name", "empresa")
            return True, f"Conectado a Alegra: {nombre}"
        except ProviderError as e:
            return False, str(e)

    def get_cartera(self, progreso_cb=None) -> list[dict]:
        if MOCK_MODE:
            return _mock_facturas()
        return self._fetch_facturas_reales(progreso_cb)

    def get_contactos(self, progreso_cb=None) -> list[dict]:
        if MOCK_MODE:
            return _mock_contactos()
        return self._fetch_contactos_reales(progreso_cb)

    # ── Implementación real (activa cuando MOCK_MODE = False) ─────────────────

    def _fetch_facturas_reales(self, progreso_cb=None) -> list[dict]:
        """
        GET /invoices?status=open&type=sale
        Alegra devuelve facturas paginadas con 'data' y 'metadata.total'.
        """
        facturas = []
        start    = 0
        limit    = 100

        while True:
            data = self._get("/invoices", {
                "type":   "sale",
                "status": "open",
                "start":  start,
                "limit":  limit,
            })

            items = data if isinstance(data, list) else data.get("data", [])
            for raw in items:
                f = _normalizar_factura(raw)
                if f:
                    facturas.append(f)

            if progreso_cb:
                progreso_cb(len(facturas), len(facturas))

            if len(items) < limit:
                break
            start += limit

        return facturas

    def _fetch_contactos_reales(self, progreso_cb=None) -> list[dict]:
        """
        GET /contacts?type=client
        """
        contactos = []
        start     = 0
        limit     = 100

        while True:
            data = self._get("/contacts", {"type": "client", "start": start, "limit": limit})
            items = data if isinstance(data, list) else data.get("data", [])
            for raw in items:
                c = _normalizar_contacto(raw)
                if c["razon_social"]:
                    contactos.append(c)
            if progreso_cb:
                progreso_cb(len(contactos), len(contactos))
            if len(items) < limit:
                break
            start += limit

        return contactos


# ── Normalización Alegra → formato interno ────────────────────────────────────

def _normalizar_factura(raw: dict) -> dict | None:
    if not raw:
        return None

    cliente_obj = raw.get("client") or {}
    cliente     = (cliente_obj.get("name") or "").strip()
    if not cliente:
        return None

    factura_no  = str(raw.get("numberTemplate", {}).get("fullNumber") or raw.get("id", ""))
    fecha_emis  = (raw.get("date") or "")[:10]           # YYYY-MM-DD
    fecha_venc  = (raw.get("dueDate") or "")[:10]

    try:
        monto = float(raw.get("total", 0) or 0)
    except (ValueError, TypeError):
        monto = 0.0

    try:
        # 'balance' en Alegra = saldo pendiente
        monto_pend = float(raw.get("balance", 0) or monto)
    except (ValueError, TypeError):
        monto_pend = monto

    if monto_pend <= 0:
        return None

    tipo = _tipo(fecha_venc)

    # Contacto embebido
    email    = (cliente_obj.get("email") or "").strip().lower()
    telefono = (cliente_obj.get("mobile") or cliente_obj.get("phone") or "").strip()
    cedula   = (cliente_obj.get("identification") or "").strip()

    # Primera línea de detalle como descripción
    items     = raw.get("items") or []
    descripcion = (items[0].get("description") or items[0].get("name") or ""
                   if items else raw.get("observations", ""))

    return {
        "factura_no":        factura_no,
        "cliente":           cliente,
        "fecha_emision":     fecha_emis,
        "fecha_vencimiento": fecha_venc,
        "descripcion":       str(descripcion),
        "monto":             monto,
        "monto_pendiente":   round(monto_pend, 2),
        "tipo":              tipo,
        "email":             email,
        "telefono":          telefono,
        "cedula_ruc":        cedula,
    }


def _normalizar_contacto(raw: dict) -> dict:
    nombre = (raw.get("name") or raw.get("nameObject", {}).get("fullName") or "").strip()
    email  = (raw.get("email") or "").strip().lower()
    tel    = (raw.get("mobile") or raw.get("phone") or "").strip()
    cedula = (raw.get("identification") or raw.get("identificationObject", {}).get("number") or "").strip()
    return {"razon_social": nombre, "email": email, "telefono": tel, "cedula_ruc": cedula}


def _tipo(fecha_venc_iso: str) -> str:
    if not fecha_venc_iso:
        return "vencida"
    try:
        return "vencida" if date.fromisoformat(fecha_venc_iso) < date.today() else "por_vencer"
    except Exception:
        return "vencida"


# ── Mock data (estructura idéntica a lo que devolvería la API real) ───────────

def _mock_facturas() -> list[dict]:
    hoy = date.today()
    return [
        {
            "factura_no": "FAC-001-001-000001", "cliente": "EMPRESA DEMO SA",
            "fecha_emision": "2024-11-01", "fecha_vencimiento": "2024-12-01",
            "descripcion": "Servicios de consultoría",
            "monto": 1500.00, "monto_pendiente": 1500.00, "tipo": "vencida",
            "email": "demo@empresa.com", "telefono": "0991234567", "cedula_ruc": "1790123456001",
        },
        {
            "factura_no": "FAC-001-001-000002", "cliente": "CLIENTE PRUEBA",
            "fecha_emision": str(hoy), "fecha_vencimiento": str(hoy),
            "descripcion": "Venta de productos",
            "monto": 800.00, "monto_pendiente": 800.00, "tipo": "por_vencer",
            "email": "prueba@cliente.ec", "telefono": "0987654321", "cedula_ruc": "0912345678",
        },
    ]


def _mock_contactos() -> list[dict]:
    return [
        {"razon_social": "EMPRESA DEMO SA",  "email": "demo@empresa.com",    "telefono": "0991234567", "cedula_ruc": "1790123456001"},
        {"razon_social": "CLIENTE PRUEBA",   "email": "prueba@cliente.ec",   "telefono": "0987654321", "cedula_ruc": "0912345678"},
    ]
