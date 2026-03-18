"""
database.py — Gestión de SQLite para Cobrador de Facturas
Tablas: contactos, plantillas, facturas_enviadas,
        facturas_cache, score_clientes, mensajes_log,
        acciones_sugeridas, config_sistema
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

            CREATE TABLE IF NOT EXISTS facturas_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                factura_no TEXT,
                cliente TEXT NOT NULL,
                fecha_emision TEXT,
                fecha_vencimiento TEXT,
                descripcion TEXT,
                monto REAL DEFAULT 0,
                monto_pendiente REAL DEFAULT 0,
                tipo TEXT,
                email TEXT,
                telefono TEXT,
                cargado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS score_clientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente TEXT UNIQUE NOT NULL,
                score REAL DEFAULT 50,
                clasificacion TEXT DEFAULT 'medio',
                dias_promedio_atraso REAL DEFAULT 0,
                total_facturas INTEGER DEFAULT 0,
                facturas_vencidas INTEGER DEFAULT 0,
                ultima_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS mensajes_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente TEXT NOT NULL,
                factura_no TEXT,
                tipo TEXT DEFAULT 'cobranza',
                canal TEXT,
                contenido TEXT,
                enviado_por TEXT DEFAULT 'manual',
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS acciones_sugeridas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente TEXT NOT NULL,
                factura_no TEXT,
                tipo TEXT NOT NULL,
                prioridad INTEGER DEFAULT 5,
                estado TEXT DEFAULT 'pendiente',
                mensaje_sugerido TEXT,
                fecha_sugerida DATE,
                fecha_completada TIMESTAMP,
                creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS config_sistema (
                clave TEXT PRIMARY KEY,
                valor TEXT
            );

            CREATE TABLE IF NOT EXISTS cargas_historial (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha_carga TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                software_origen TEXT,
                n_facturas INTEGER DEFAULT 0,
                monto_total REAL DEFAULT 0,
                nombre_archivo TEXT
            );

            CREATE TABLE IF NOT EXISTS cargas_snapshot (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                carga_id INTEGER NOT NULL REFERENCES cargas_historial(id) ON DELETE CASCADE,
                factura_no TEXT,
                cliente TEXT,
                fecha_emision TEXT,
                fecha_vencimiento TEXT,
                descripcion TEXT,
                monto REAL DEFAULT 0,
                monto_pendiente REAL DEFAULT 0,
                tipo TEXT,
                email TEXT,
                telefono TEXT
            );

            CREATE TABLE IF NOT EXISTS cotizaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente TEXT NOT NULL,
                contacto_id INTEGER REFERENCES contactos(id) ON DELETE SET NULL,
                email TEXT,
                telefono TEXT,
                estado TEXT DEFAULT 'pendiente',
                validez_dias INTEGER DEFAULT 30,
                notas TEXT,
                total REAL DEFAULT 0,
                creada_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                actualizada_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS cotizacion_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cotizacion_id INTEGER NOT NULL REFERENCES cotizaciones(id) ON DELETE CASCADE,
                descripcion TEXT NOT NULL,
                cantidad REAL DEFAULT 1,
                precio_unit REAL DEFAULT 0,
                total REAL DEFAULT 0
            );
        """)

        # Migración: agregar columna monto a facturas_enviadas si no existe
        try:
            conn.execute("ALTER TABLE facturas_enviadas ADD COLUMN monto REAL DEFAULT 0")
            conn.commit()
        except Exception:
            pass  # La columna ya existe

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
                email    = COALESCE(NULLIF(excluded.email, ''),    contactos.email),
                telefono = COALESCE(NULLIF(excluded.telefono, ''), contactos.telefono),
                fuente = excluded.fuente,
                confianza = excluded.confianza,
                actualizado_en = CURRENT_TIMESTAMP
        """, (nombre_contifico, nombre_contifico.strip().upper(),
              email or None, telefono or None, fuente, confianza))
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

def registrar_envio(factura_no: str, cliente: str, canal: str,
                    estado: str = "ok", monto: float = 0.0):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO facturas_enviadas (factura_no, cliente, canal, estado, monto) VALUES (?, ?, ?, ?, ?)",
            (factura_no, cliente, canal, estado, monto)
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


# ─── Facturas cache ─────────────────────────────────────────────────────────

def guardar_facturas_cache(facturas: list[dict]):
    """Reemplaza el cache de facturas con el nuevo lote."""
    with get_connection() as conn:
        conn.execute("DELETE FROM facturas_cache")
        for f in facturas:
            conn.execute("""
                INSERT INTO facturas_cache
                    (factura_no, cliente, fecha_emision, fecha_vencimiento,
                     descripcion, monto, monto_pendiente, tipo, email, telefono)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                f.get("factura_no") or f.get("numero", ""),
                f.get("cliente", ""),
                f.get("fecha_emision", ""),
                f.get("fecha_vencimiento", ""),
                f.get("descripcion", ""),
                float(f.get("monto", 0) or 0),
                float(f.get("monto_pendiente", f.get("saldo", 0)) or 0),
                f.get("tipo") or f.get("estado", ""),
                f.get("email", ""),
                f.get("telefono", ""),
            ))
        conn.commit()


def get_facturas_cache() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM facturas_cache ORDER BY tipo DESC, cliente"
        ).fetchall()
        return [dict(r) for r in rows]


# ─── Score de clientes ───────────────────────────────────────────────────────

def upsert_score(cliente: str, score: float, clasificacion: str,
                 dias_promedio: float, total: int, vencidas: int):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO score_clientes
                (cliente, score, clasificacion, dias_promedio_atraso,
                 total_facturas, facturas_vencidas, ultima_actualizacion)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(cliente) DO UPDATE SET
                score = excluded.score,
                clasificacion = excluded.clasificacion,
                dias_promedio_atraso = excluded.dias_promedio_atraso,
                total_facturas = excluded.total_facturas,
                facturas_vencidas = excluded.facturas_vencidas,
                ultima_actualizacion = CURRENT_TIMESTAMP
        """, (cliente, score, clasificacion, dias_promedio, total, vencidas))
        conn.commit()


def get_score(cliente: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM score_clientes WHERE cliente = ?", (cliente,)
        ).fetchone()
        return dict(row) if row else None


def get_todos_scores() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM score_clientes ORDER BY score DESC"
        ).fetchall()
        return [dict(r) for r in rows]


# ─── Mensajes log ───────────────────────────────────────────────────────────

def registrar_mensaje_log(cliente: str, factura_no: str, tipo: str,
                           canal: str, contenido: str, enviado_por: str = "manual"):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO mensajes_log (cliente, factura_no, tipo, canal, contenido, enviado_por)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (cliente, factura_no, tipo, canal, contenido, enviado_por))
        conn.commit()


def get_mensajes_log(cliente: str = None, limit: int = 100) -> list[dict]:
    with get_connection() as conn:
        if cliente:
            rows = conn.execute("""
                SELECT * FROM mensajes_log WHERE cliente = ?
                ORDER BY fecha DESC LIMIT ?
            """, (cliente, limit)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM mensajes_log ORDER BY fecha DESC LIMIT ?
            """, (limit,)).fetchall()
        return [dict(r) for r in rows]


def get_actividad_reciente(limit: int = 20) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT * FROM mensajes_log ORDER BY fecha DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]


# ─── Acciones sugeridas ──────────────────────────────────────────────────────

def crear_accion(cliente: str, factura_no: str, tipo: str, prioridad: int,
                 mensaje_sugerido: str, fecha_sugerida: str):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO acciones_sugeridas
                (cliente, factura_no, tipo, prioridad, mensaje_sugerido, fecha_sugerida)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (cliente, factura_no, tipo, prioridad, mensaje_sugerido, fecha_sugerida))
        conn.commit()


def get_acciones_pendientes(fecha: str = None) -> list[dict]:
    with get_connection() as conn:
        if fecha:
            rows = conn.execute("""
                SELECT * FROM acciones_sugeridas
                WHERE estado = 'pendiente' AND fecha_sugerida <= ?
                ORDER BY prioridad ASC, creado_en ASC
            """, (fecha,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM acciones_sugeridas
                WHERE estado = 'pendiente'
                ORDER BY prioridad ASC, creado_en ASC
            """).fetchall()
        return [dict(r) for r in rows]


def completar_accion(accion_id: int):
    with get_connection() as conn:
        conn.execute("""
            UPDATE acciones_sugeridas
            SET estado = 'completada', fecha_completada = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (accion_id,))
        conn.commit()


def posponer_accion(accion_id: int, nueva_fecha: str):
    with get_connection() as conn:
        conn.execute("""
            UPDATE acciones_sugeridas
            SET estado = 'pendiente', fecha_sugerida = ?
            WHERE id = ?
        """, (nueva_fecha, accion_id))
        conn.commit()


def limpiar_acciones_antiguas():
    """Elimina acciones completadas o pospuestas de más de 30 días."""
    with get_connection() as conn:
        conn.execute("""
            DELETE FROM acciones_sugeridas
            WHERE estado != 'pendiente'
            AND creado_en < datetime('now', '-30 days')
        """)
        conn.commit()


def hay_accion_pendiente_hoy(cliente: str, factura_no: str) -> bool:
    with get_connection() as conn:
        count = conn.execute("""
            SELECT COUNT(*) FROM acciones_sugeridas
            WHERE cliente = ? AND factura_no = ? AND estado = 'pendiente'
            AND fecha_sugerida = DATE('now')
        """, (cliente, factura_no)).fetchone()[0]
        return count > 0


# ─── Config sistema ──────────────────────────────────────────────────────────

def get_config_sistema(clave: str, default: str = "") -> str:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT valor FROM config_sistema WHERE clave = ?", (clave,)
        ).fetchone()
        return row[0] if row else default


def set_config_sistema(clave: str, valor: str):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO config_sistema (clave, valor) VALUES (?, ?)
            ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor
        """, (clave, valor))
        conn.commit()


# ─── Historial de cargas ─────────────────────────────────────────────────────

def registrar_carga_historial(software: str, n_facturas: int, monto_total: float,
                               nombre_archivo: str, facturas: list[dict]) -> int:
    """
    Guarda metadatos + snapshot completo de la carga actual.
    Retorna el id de la carga creada.
    """
    with get_connection() as conn:
        cur = conn.execute("""
            INSERT INTO cargas_historial (software_origen, n_facturas, monto_total, nombre_archivo)
            VALUES (?, ?, ?, ?)
        """, (software, n_facturas, round(monto_total, 2), nombre_archivo))
        carga_id = cur.lastrowid

        for f in facturas:
            conn.execute("""
                INSERT INTO cargas_snapshot
                    (carga_id, factura_no, cliente, fecha_emision, fecha_vencimiento,
                     descripcion, monto, monto_pendiente, tipo, email, telefono)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                carga_id,
                f.get("factura_no", ""),
                f.get("cliente", ""),
                f.get("fecha_emision", ""),
                f.get("fecha_vencimiento", ""),
                f.get("descripcion", ""),
                float(f.get("monto", 0) or 0),
                float(f.get("monto_pendiente", 0) or 0),
                f.get("tipo", ""),
                f.get("email", ""),
                f.get("telefono", ""),
            ))
        conn.commit()
    return carga_id


def get_historial_cargas(limit: int = 10) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id, fecha_carga, software_origen, n_facturas, monto_total, nombre_archivo
            FROM cargas_historial
            ORDER BY fecha_carga DESC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]


def restaurar_desde_historial(carga_id: int) -> list[dict]:
    """Retorna las facturas del snapshot de esa carga, en el formato interno estándar."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT factura_no, cliente, fecha_emision, fecha_vencimiento,
                   descripcion, monto, monto_pendiente, tipo, email, telefono
            FROM cargas_snapshot
            WHERE carga_id = ?
            ORDER BY tipo DESC, cliente
        """, (carga_id,)).fetchall()
        return [dict(r) for r in rows]


def eliminar_carga_historial(carga_id: int):
    """Elimina la carga y su snapshot (ON DELETE CASCADE)."""
    with get_connection() as conn:
        conn.execute("DELETE FROM cargas_historial WHERE id = ?", (carga_id,))
        conn.commit()


def limpiar_historial_antiguo(mantener: int = 5):
    """Deja solo las N cargas más recientes, borra las demás con sus snapshots."""
    with get_connection() as conn:
        ids_mantener = conn.execute("""
            SELECT id FROM cargas_historial ORDER BY fecha_carga DESC LIMIT ?
        """, (mantener,)).fetchall()
        if not ids_mantener:
            return
        placeholders = ",".join("?" * len(ids_mantener))
        ids = [r[0] for r in ids_mantener]
        conn.execute(
            f"DELETE FROM cargas_historial WHERE id NOT IN ({placeholders})", ids
        )
        conn.commit()


# ─── Estadísticas ─────────────────────────────────────────────────────────────

def get_estadisticas_por_mes(meses: int = 6) -> list[dict]:
    """
    Retorna actividad de envíos por mes: cantidad y monto gestionado.
    Los meses sin actividad se omiten.
    """
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT
                strftime('%Y-%m', fecha_envio)  AS mes,
                SUM(CASE WHEN estado != 'error' THEN 1 ELSE 0 END) AS n_enviados,
                SUM(CASE WHEN estado != 'error' THEN COALESCE(monto, 0) ELSE 0 END) AS monto_gestionado,
                SUM(CASE WHEN estado = 'error' THEN 1 ELSE 0 END) AS n_errores
            FROM facturas_enviadas
            WHERE fecha_envio >= datetime('now', ? || ' months')
            GROUP BY mes
            ORDER BY mes
        """, (f"-{meses}",)).fetchall()
        return [dict(r) for r in rows]


# ─── Cotizaciones ─────────────────────────────────────────────────────────────

def crear_cotizacion(cliente: str, contacto_id: int | None, email: str,
                     telefono: str, validez_dias: int, notas: str,
                     items: list[dict]) -> int:
    """
    Crea una cotización con sus ítems. Retorna el id de la cotización creada.
    Cada ítem debe tener: descripcion, cantidad, precio_unit.
    """
    total = sum(float(i.get("cantidad", 1)) * float(i.get("precio_unit", 0))
                for i in items)
    with get_connection() as conn:
        cur = conn.execute("""
            INSERT INTO cotizaciones
                (cliente, contacto_id, email, telefono, validez_dias, notas, total)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (cliente, contacto_id, email, telefono, validez_dias, notas, round(total, 2)))
        cot_id = cur.lastrowid
        for i in items:
            cant   = float(i.get("cantidad", 1))
            precio = float(i.get("precio_unit", 0))
            conn.execute("""
                INSERT INTO cotizacion_items (cotizacion_id, descripcion, cantidad, precio_unit, total)
                VALUES (?, ?, ?, ?, ?)
            """, (cot_id, i.get("descripcion", ""), cant, precio, round(cant * precio, 2)))
        conn.commit()
    return cot_id


def get_cotizacion(cotizacion_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM cotizaciones WHERE id = ?", (cotizacion_id,)
        ).fetchone()
        return dict(row) if row else None


def get_cotizaciones(estado: str | None = None) -> list[dict]:
    with get_connection() as conn:
        if estado:
            rows = conn.execute("""
                SELECT * FROM cotizaciones WHERE estado = ?
                ORDER BY creada_en DESC
            """, (estado,)).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM cotizaciones ORDER BY creada_en DESC"
            ).fetchall()
        return [dict(r) for r in rows]


def get_items_cotizacion(cotizacion_id: int) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM cotizacion_items WHERE cotizacion_id = ? ORDER BY id",
            (cotizacion_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def actualizar_estado_cotizacion(cotizacion_id: int, estado: str):
    with get_connection() as conn:
        conn.execute("""
            UPDATE cotizaciones
            SET estado = ?, actualizada_en = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (estado, cotizacion_id))
        conn.commit()


def actualizar_cotizacion(cotizacion_id: int, cliente: str, contacto_id: int | None,
                          email: str, telefono: str, validez_dias: int,
                          notas: str, items: list[dict]):
    """Reemplaza todos los datos de una cotización existente y sus ítems."""
    total = sum(float(i.get("cantidad", 1)) * float(i.get("precio_unit", 0))
                for i in items)
    with get_connection() as conn:
        conn.execute("""
            UPDATE cotizaciones
            SET cliente = ?, contacto_id = ?, email = ?, telefono = ?,
                validez_dias = ?, notas = ?, total = ?, actualizada_en = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (cliente, contacto_id, email, telefono, validez_dias, notas,
              round(total, 2), cotizacion_id))
        conn.execute("DELETE FROM cotizacion_items WHERE cotizacion_id = ?", (cotizacion_id,))
        for i in items:
            cant   = float(i.get("cantidad", 1))
            precio = float(i.get("precio_unit", 0))
            conn.execute("""
                INSERT INTO cotizacion_items (cotizacion_id, descripcion, cantidad, precio_unit, total)
                VALUES (?, ?, ?, ?, ?)
            """, (cotizacion_id, i.get("descripcion", ""), cant, precio, round(cant * precio, 2)))
        conn.commit()


def eliminar_cotizacion(cotizacion_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM cotizaciones WHERE id = ?", (cotizacion_id,))
        conn.commit()


def buscar_contactos_para_cotizacion(query: str, limit: int = 10) -> list[dict]:
    """Búsqueda parcial en contactos para el autocomplete del campo cliente."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id, nombre_contifico, email, telefono
            FROM contactos
            WHERE nombre_contifico LIKE ?
            ORDER BY nombre_contifico
            LIMIT ?
        """, (f"%{query}%", limit)).fetchall()
        return [dict(r) for r in rows]
