"""
contifico_service.py — Cliente para la API REST de Contifico

Documentación de la API: https://api.contifico.com/sistema/api/v1/
Autenticación: header  Authorization: Token <api_token>

Endpoints usados:
  GET /persona/     → lista de personas/clientes con email y teléfono
  GET /documento/   → (opcional) facturas por cobrar
"""

import urllib.request
import urllib.error
import urllib.parse
import json
from typing import Optional

BASE_URL = "https://api.contifico.com/sistema/api/v1"


class ContificoService:
    """Wrapper sobre la API REST de Contifico usando solo stdlib."""

    def __init__(self, api_token: str):
        self.api_token = api_token.strip()

    def _get(self, endpoint: str, params: Optional[dict] = None) -> dict | list:
        """GET autenticado. Lanza ContificoError si falla."""
        url = f"{BASE_URL}{endpoint}"
        if params:
            url += "?" + urllib.parse.urlencode(params)

        req = urllib.request.Request(url)
        req.add_header("Authorization", self.api_token)
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:200]
            if e.code == 401:
                raise ContificoError("Token inválido o sin autorización (401)")
            if e.code == 403:
                raise ContificoError("Acceso denegado (403). Verifica los permisos del token.")
            raise ContificoError(f"Error HTTP {e.code}: {body}")
        except urllib.error.URLError as e:
            raise ContificoError(f"Sin conexión a internet o URL incorrecta: {e.reason}")
        except Exception as e:
            raise ContificoError(str(e))

    # ── Verificación ──────────────────────────────────────────────────────

    def verificar_conexion(self) -> tuple[bool, str]:
        """Prueba el token intentando listar la primera persona."""
        try:
            self._get("/persona/", {"limit": 1})
            return True, "Conexión exitosa"
        except ContificoError as e:
            return False, str(e)

    # ── Clientes ──────────────────────────────────────────────────────────

    def get_clientes(self, progreso_cb=None) -> list[dict]:
        """
        Devuelve todos los clientes de Contifico.
        Cada item del resultado es un dict con al menos:
          razon_social, email, telefono, cedula_ruc
        progreso_cb: función opcional(actual: int, total: int) para reportar avance
        """
        clientes = []
        offset = 0
        limit = 100
        total = None

        while True:
            data = self._get("/persona/", {"limit": limit, "offset": offset})

            # La API puede devolver lista directa o paginación {count, results}
            if isinstance(data, list):
                clientes.extend([_normalizar_cliente(c) for c in data])
                break
            else:
                results = data.get("results", data.get("data", []))
                total = data.get("count", total)
                clientes.extend([_normalizar_cliente(c) for c in results])

                if progreso_cb and total:
                    progreso_cb(len(clientes), total)

                next_url = data.get("next")
                if not next_url or not results:
                    break
                offset += limit

        return clientes


# ── Normalización de campos ───────────────────────────────────────────────────

def _normalizar_cliente(raw: dict) -> dict:
    """
    Contifico puede usar distintos nombres de campo según la versión.
    Devolvemos siempre los mismos campos: razon_social, email, telefono, cedula_ruc.
    """
    nombre = (
        raw.get("razon_social")
        or raw.get("nombre")
        or raw.get("nombre_comercial")
        or ""
    ).strip()

    email = (
        raw.get("correo_1")
        or raw.get("correo")
        or raw.get("email")
        or ""
    ).strip().lower()

    # Contifico a veces devuelve múltiples correos separados por coma
    if "," in email:
        email = email.split(",")[0].strip()

    telefono = (
        raw.get("telefono")
        or raw.get("celular")
        or raw.get("telefono_1")
        or ""
    ).strip()

    cedula = (
        raw.get("cedula_ruc")
        or raw.get("ruc")
        or raw.get("cedula")
        or ""
    ).strip()

    return {
        "razon_social": nombre,
        "email":        email,
        "telefono":     telefono,
        "cedula_ruc":   cedula,
    }


class ContificoError(Exception):
    pass
