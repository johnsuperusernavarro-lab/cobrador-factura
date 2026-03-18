"""
core/base_provider.py — Contrato que debe cumplir cualquier sistema contable.

Para agregar soporte a un nuevo software (Alegra, Monica, Quickbooks, etc.):
  1. Crea core/providers/<nombre>_provider.py
  2. Hereda de AccountingProvider
  3. Implementa los 3 métodos abstractos
  4. Registra el proveedor en core/providers/__init__.py

Formato estandarizado de retorno
─────────────────────────────────
Factura:
  {
    "cliente":           str,
    "factura_no":        str,
    "fecha_emision":     str,   # YYYY-MM-DD  o  DD/MM/YYYY
    "fecha_vencimiento": str,
    "descripcion":       str,
    "monto":             float,
    "monto_pendiente":   float,
    "tipo":              str,   # "vencida" | "por_vencer"
    "email":             str,   # opcional
    "telefono":          str,   # opcional
    "cedula_ruc":        str,   # opcional
  }

Contacto:
  {
    "razon_social": str,
    "email":        str,
    "telefono":     str,
    "cedula_ruc":   str,
  }
"""

from abc import ABC, abstractmethod


class AccountingProvider(ABC):
    """Interfaz estándar para cualquier sistema contable."""

    # ── Identificación ────────────────────────────────────────────────────────

    @property
    @abstractmethod
    def nombre(self) -> str:
        """Nombre legible del proveedor, p.ej. 'Contifico', 'Alegra'."""

    # ── Conexión ──────────────────────────────────────────────────────────────

    @abstractmethod
    def verificar_conexion(self) -> tuple[bool, str]:
        """
        Prueba que las credenciales son válidas.
        Retorna (ok: bool, mensaje: str).
        """

    # ── Datos ─────────────────────────────────────────────────────────────────

    @abstractmethod
    def get_cartera(self, progreso_cb=None) -> list[dict]:
        """
        Retorna todas las facturas con saldo pendiente.
        Formato: ver módulo docstring.
        progreso_cb: callable(actual: int, total: int) opcional.
        """

    @abstractmethod
    def get_contactos(self, progreso_cb=None) -> list[dict]:
        """
        Retorna todos los clientes con datos de contacto.
        Formato: ver módulo docstring.
        """


class ProviderError(Exception):
    """Error genérico de proveedor contable."""
