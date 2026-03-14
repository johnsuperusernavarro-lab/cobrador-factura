"""
database.py — Gestión de SQLite para Cobrador de Facturas
Tablas: contactos, plantillas, facturas_enviadas
"""

import sqlite3
from pathlib import Path
from datetime import datetime

from app.utils import get_data_dir

DB_PATH = get_data_dir() / "cobros.db"

# ─── Plantillas por defecto ────────────────────────────────────────────────

_DATOS_BANCARIOS_EMAIL = (
    "Para realizar el pago por transferencia:\n"
    "   Banco   : [TU BANCO]\n"
    "   Nombre  : [TITULAR DE CUENTA]\n"
    "   Cta. Corriente: [NÚMERO DE CUENTA]\n"
    "   C.I.    : [CÉDULA]\n"
)

_DATOS_BANCARIOS_WA = (
    "Para transferencia bancaria:\n"
    "*[TU BANCO]*\n"
    "[TITULAR DE CUENTA]\n"
    "Cta. Corriente: *[NÚMERO DE CUENTA]*\n"
    "C.I.: [CÉDULA]"
)

_FIRMA_EMAIL = (
    "\nSaludos cordiales,\n\n"
    "[TU NOMBRE]\n"
    "[TU EMPRESA] - [TU CARGO]\n"
    "Tel: [TELÉFONO] | Email: [TU CORREO]\n"
)

_FIRMA_WA = (
    "Saludos,\n"
    "*[TU NOMBRE]*\n"
    "[TU EMPRESA]\n"
    "[TELÉFONO]"
)

PLANTILLAS_DEFAULT = [
    {
        "tipo": "por_vencer",
        "canal": "email",
        "asunto": "Factura N° {factura_no} - {empresa}",
        "cuerpo": (
            "Estimados señores {cliente},\n\n"
            "Por medio del presente, nos permitimos hacer llegar la factura "
            "N° {factura_no} con fecha {fecha}, "
            "correspondiente a {descripcion}, por un valor de ${total}.\n\n"
            "Adjunto encontrarán el comprobante electrónico para su registro.\n\n"
            + _DATOS_BANCARIOS_EMAIL
            + "\nQuedo a su entera disposición para cualquier consulta o "
            "confirmación de recepción.\n"
            + _FIRMA_EMAIL
        ),
    },
    {
        "tipo": "por_vencer",
        "canal": "whatsapp",
        "asunto": "",
        "cuerpo": (
            "Estimados *{cliente}*,\n\n"
            "Por este medio les hacemos llegar la factura "
            "*N° {factura_no}* con fecha {fecha}, "
            "correspondiente a _{descripcion}_, "
            "por un valor de *${total}*.\n\n"
            "El comprobante fue enviado a su correo electrónico registrado.\n\n"
            + _DATOS_BANCARIOS_WA
            + "\n\nQuedo atento a cualquier consulta.\n\n"
            + _FIRMA_WA
        ),
    },
    {
        "tipo": "vencida",
        "canal": "email",
        "asunto": "Recordatorio de pago - Factura N° {factura_no} - {empresa}",
        "cuerpo": (
            "Estimados señores {cliente},\n\n"
            "Esperamos que se encuentren bien. Nos permitimos recordarles "
            "que la factura N° {factura_no} con fecha {fecha}, "
            "por un valor de ${total}, se encuentra pendiente de pago.\n\n"
            "Les agradecemos gestionar el pago a la brevedad posible. "
            "Para su comodidad, los datos bancarios son:\n\n"
            + _DATOS_BANCARIOS_EMAIL
            + "\nAdjunto el comprobante para su referencia. Ante cualquier "
            "inconveniente, quedamos a su disposición.\n"
            + _FIRMA_EMAIL
        ),
    },
    {
        "tipo": "vencida",
        "canal": "whatsapp",
        "asunto": "",
        "cuerpo": (
            "Estimados *{cliente}*,\n\n"
            "Esperamos que se encuentren bien. Les recordamos que la factura "
            "*N° {factura_no}* con fecha {fecha}, "
            "por un valor de *${total}*, "
            "se encuentra pendiente de pago.\n\n"
            "Les agradecemos gestionar el pago a la brevedad. "
            "Pueden realizarlo mediante transferencia bancaria:\n\n"
            + _DATOS_BANCARIOS_WA
            + "\n\nAdjunto el comprobante en su correo. Quedo atento a su "
            "confirmación de pago.\n\n"
            + _FIRMA_WA
        ),
    },
]


# ─── Conexión ──────────────────────────────────────────────────────────────

def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Crea tablas e inserta plantillas por defecto si no existen."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS contactos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre_contifico TEXT UNIQUE NOT NULL,
                nombre_normalizado TEXT,
                email TEXT,
                telefono TEXT,
                fuente TEXT DEFAULT 'manual',
                confianza REAL DEFAULT 1.0,
                actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS plantillas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT NOT NULL,
                canal TEXT NOT NULL,
                asunto TEXT,
                cuerpo TEXT NOT NULL,
                actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(tipo, canal)
            );

            CREATE TABLE IF NOT EXISTS facturas_enviadas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                factura_no TEXT,
                cliente TEXT,
                canal TEXT,
                estado TEXT DEFAULT 'ok',
                fecha_envio TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Insertar plantillas por defecto solo si la tabla está vacía
        count = conn.execute("SELECT COUNT(*) FROM plantillas").fetchone()[0]
        if count == 0:
            now = datetime.now().isoformat()
            for p in PLANTILLAS_DEFAULT:
                conn.execute(
                    "INSERT OR IGNORE INTO plantillas (tipo, canal, asunto, cuerpo, actualizado_en) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (p["tipo"], p["canal"], p["asunto"], p["cuerpo"], now)
                )
        conn.commit()


# ─── Contactos ─────────────────────────────────────────────────────────────

def upsert_contacto(nombre_contifico: str, email: str = None,
                    telefono: str = None, fuente: str = "manual",
                    confianza: float = 1.0):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO contactos (nombre_contifico, nombre_normalizado, email, telefono, fuente, confianza, actualizado_en)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(nombre_contifico) DO UPDATE SET
                email = COALESCE(excluded.email, contactos.email),
                telefono = COALESCE(excluded.telefono, contactos.telefono),
                fuente = excluded.fuente,
                confianza = excluded.confianza,
                actualizado_en = CURRENT_TIMESTAMP
        """, (nombre_contifico, nombre_contifico.strip().upper(),
              email, telefono, fuente, confianza))
        conn.commit()


def get_contacto(nombre_contifico: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM contactos WHERE nombre_contifico = ?",
            (nombre_contifico,)
        ).fetchone()
        return dict(row) if row else None


def get_todos_contactos() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM contactos ORDER BY nombre_contifico"
        ).fetchall()
        return [dict(r) for r in rows]


# ─── Plantillas ────────────────────────────────────────────────────────────

def get_plantilla(tipo: str, canal: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM plantillas WHERE tipo = ? AND canal = ?",
            (tipo, canal)
        ).fetchone()
        return dict(row) if row else None


def get_todas_plantillas() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM plantillas ORDER BY tipo, canal"
        ).fetchall()
        return [dict(r) for r in rows]


def save_plantilla(tipo: str, canal: str, asunto: str, cuerpo: str):
    with get_connection() as conn:
        conn.execute("""
            UPDATE plantillas SET asunto = ?, cuerpo = ?, actualizado_en = CURRENT_TIMESTAMP
            WHERE tipo = ? AND canal = ?
        """, (asunto, cuerpo, tipo, canal))
        conn.commit()


# ─── Historial ─────────────────────────────────────────────────────────────

def registrar_envio(factura_no: str, cliente: str, canal: str, estado: str = "ok"):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO facturas_enviadas (factura_no, cliente, canal, estado) VALUES (?, ?, ?, ?)",
            (factura_no, cliente, canal, estado)
        )
        conn.commit()


def get_enviados_hoy() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT * FROM facturas_enviadas
            WHERE DATE(fecha_envio) = DATE('now')
            ORDER BY fecha_envio DESC
        """).fetchall()
        return [dict(r) for r in rows]


def ya_fue_enviado_hoy(factura_no: str, canal: str) -> bool:
    with get_connection() as conn:
        count = conn.execute("""
            SELECT COUNT(*) FROM facturas_enviadas
            WHERE factura_no = ? AND canal = ? AND DATE(fecha_envio) = DATE('now')
        """, (factura_no, canal)).fetchone()[0]
        return count > 0
