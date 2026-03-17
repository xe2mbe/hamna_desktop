"""
HAMNA Desktop — Capa de Base de Datos (SQLite)
Python 3.13 · Windows 10/11
"""
import sqlite3
import os
from pathlib import Path

DB_PATH = Path(__file__).parent / "hamna.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db() -> None:
    conn = get_connection()
    c = conn.cursor()

    # ── Tablas base ────────────────────────────────────────────────────────────
    c.executescript("""
        CREATE TABLE IF NOT EXISTS eventos_type (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre  TEXT NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS eventos (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre         TEXT NOT NULL,
            tipo_evento_id INTEGER REFERENCES eventos_type(id),
            creado_en      DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS tipos_seccion (
            id     INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS secciones (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre          TEXT NOT NULL,
            tipo_seccion_id INTEGER REFERENCES tipos_seccion(id),
            ruta_archivo    TEXT,
            texto_tts       TEXT,
            duracion        REAL DEFAULT 0,
            creado_en       DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS programacion (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            evento_id   INTEGER NOT NULL REFERENCES eventos(id) ON DELETE CASCADE,
            fecha       TEXT NOT NULL,
            hora        TEXT NOT NULL,
            recurrencia TEXT DEFAULT 'ninguna',
            activo      INTEGER DEFAULT 1
        );
    """)

    # ── Migración: tabla evento_secciones (many-to-many) ──────────────────────
    c.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='evento_secciones'"
    )
    if not c.fetchone():
        # Verificar si secciones aún tiene la columna evento_id (esquema antiguo)
        c.execute("PRAGMA table_info(secciones)")
        col_names = [row[1] for row in c.fetchall()]

        # Crear tabla de unión
        conn.execute("""
            CREATE TABLE evento_secciones (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                evento_id  INTEGER NOT NULL REFERENCES eventos(id) ON DELETE CASCADE,
                seccion_id INTEGER NOT NULL REFERENCES secciones(id) ON DELETE CASCADE,
                orden      INTEGER DEFAULT 0,
                UNIQUE(evento_id, seccion_id)
            )
        """)

        if "evento_id" in col_names:
            # Migrar datos existentes al join table
            conn.execute("""
                INSERT INTO evento_secciones (evento_id, seccion_id, orden)
                SELECT evento_id, id, id FROM secciones WHERE evento_id IS NOT NULL
            """)
            # Recrear secciones sin evento_id
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("""
                CREATE TABLE secciones_new (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre          TEXT NOT NULL,
                    tipo_seccion_id INTEGER REFERENCES tipos_seccion(id),
                    ruta_archivo    TEXT,
                    texto_tts       TEXT,
                    duracion        REAL DEFAULT 0,
                    creado_en       DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                INSERT INTO secciones_new
                    (id, nombre, tipo_seccion_id, ruta_archivo,
                     texto_tts, duracion, creado_en)
                SELECT id, nombre, tipo_seccion_id, ruta_archivo,
                       texto_tts, duracion, creado_en
                FROM secciones
            """)
            conn.execute("DROP TABLE secciones")
            conn.execute("ALTER TABLE secciones_new RENAME TO secciones")
            conn.execute("PRAGMA foreign_keys = ON")

        conn.commit()

    # ── Migración: columna contabilizable en evento_secciones ────────────────
    es_cols = [r[1] for r in c.execute(
        "PRAGMA table_info(evento_secciones)").fetchall()]
    if "contabilizable" not in es_cols:
        conn.execute(
            "ALTER TABLE evento_secciones ADD COLUMN contabilizable INTEGER DEFAULT 1"
        )
        conn.commit()

    # ── Migración: columna numero en eventos ──────────────────────────────────
    ev_cols = [r[1] for r in c.execute("PRAGMA table_info(eventos)").fetchall()]
    if "numero" not in ev_cols:
        conn.execute("ALTER TABLE eventos ADD COLUMN numero INTEGER")
        conn.commit()

    # ── Migración: columna regenerar_antes en secciones ───────────────────────
    cols = [r[1] for r in c.execute("PRAGMA table_info(secciones)").fetchall()]
    if "regenerar_antes" not in cols:
        conn.execute(
            "ALTER TABLE secciones ADD COLUMN regenerar_antes INTEGER DEFAULT 0"
        )
        conn.commit()

    # ── Seed eventos_type ──────────────────────────────────────────────────────
    c.execute("SELECT COUNT(*) FROM eventos_type")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO eventos_type (nombre) VALUES (?)", [
            ("Transmisión en Vivo",), ("Grabación",),
            ("Programa Diferido",), ("Boletín",), ("Especial",),
        ])

    # ── Seed tipos_seccion ─────────────────────────────────────────────────────
    c.execute("SELECT COUNT(*) FROM tipos_seccion")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO tipos_seccion (nombre) VALUES (?)", [
            ("TTS",), ("Audio",), ("Sonido",),
        ])

    conn.commit()
    conn.close()


# ── eventos_type ───────────────────────────────────────────────────────────────
def get_eventos_types() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT id, nombre FROM eventos_type ORDER BY nombre"
        ).fetchall()


# ── eventos ────────────────────────────────────────────────────────────────────
def insert_evento(nombre: str, tipo_evento_id: int,
                   numero: int = None) -> int:
    with get_connection() as conn:
        c = conn.execute(
            "INSERT INTO eventos (nombre, tipo_evento_id, numero) VALUES (?, ?, ?)",
            (nombre, tipo_evento_id, numero)
        )
        conn.commit()
        return c.lastrowid


def get_all_eventos() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute("""
            SELECT e.id, e.nombre, e.numero, et.nombre AS tipo, e.creado_en
            FROM eventos e
            LEFT JOIN eventos_type et ON et.id = e.tipo_evento_id
            ORDER BY e.creado_en DESC
        """).fetchall()


def update_evento(evento_id: int, nombre: str, tipo_evento_id: int,
                  numero: int = None) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE eventos SET nombre=?, tipo_evento_id=?, numero=? WHERE id=?",
            (nombre, tipo_evento_id, numero, evento_id)
        )
        conn.commit()


def delete_evento(evento_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM eventos WHERE id=?", (evento_id,))
        conn.commit()


# ── tipos_seccion ──────────────────────────────────────────────────────────────
def get_tipos_seccion() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT id, nombre FROM tipos_seccion ORDER BY id"
        ).fetchall()


# ── secciones ──────────────────────────────────────────────────────────────────
def insert_seccion(nombre: str, tipo_seccion_id: int,
                   ruta_archivo: str = None, texto_tts: str = None,
                   duracion: float = 0,
                   regenerar_antes: bool = False) -> int:
    with get_connection() as conn:
        c = conn.execute("""
            INSERT INTO secciones
            (nombre, tipo_seccion_id, ruta_archivo, texto_tts, duracion, regenerar_antes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (nombre, tipo_seccion_id, ruta_archivo, texto_tts, duracion,
              int(regenerar_antes)))
        conn.commit()
        return c.lastrowid


def update_seccion(seccion_id: int, nombre: str, ruta_archivo: str = None,
                   texto_tts: str = None, duracion: float = None,
                   regenerar_antes: bool = None) -> None:
    with get_connection() as conn:
        fields, vals = [], []
        fields.append("nombre=?"); vals.append(nombre)
        if ruta_archivo is not None:
            fields.append("ruta_archivo=?"); vals.append(ruta_archivo)
        if texto_tts is not None:
            fields.append("texto_tts=?"); vals.append(texto_tts)
        if duracion is not None:
            fields.append("duracion=?"); vals.append(duracion)
        if regenerar_antes is not None:
            fields.append("regenerar_antes=?"); vals.append(int(regenerar_antes))
        vals.append(seccion_id)
        conn.execute(f"UPDATE secciones SET {', '.join(fields)} WHERE id=?", vals)
        conn.commit()


def update_seccion_ruta(seccion_id: int, ruta: str) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE secciones SET ruta_archivo=? WHERE id=?",
                     (ruta, seccion_id))
        conn.commit()


def get_all_secciones() -> list[sqlite3.Row]:
    """Todas las secciones de la biblioteca (sin filtro de evento)."""
    with get_connection() as conn:
        return conn.execute("""
            SELECT s.id, s.nombre, ts.nombre AS tipo,
                   s.ruta_archivo, s.texto_tts, s.duracion, s.creado_en,
                   s.regenerar_antes
            FROM secciones s
            LEFT JOIN tipos_seccion ts ON ts.id = s.tipo_seccion_id
            ORDER BY s.nombre
        """).fetchall()


def get_seccion_by_id(seccion_id: int) -> sqlite3.Row:
    with get_connection() as conn:
        return conn.execute("""
            SELECT s.id, s.nombre, ts.nombre AS tipo, s.tipo_seccion_id,
                   s.ruta_archivo, s.texto_tts, s.duracion, s.creado_en,
                   s.regenerar_antes
            FROM secciones s
            LEFT JOIN tipos_seccion ts ON ts.id = s.tipo_seccion_id
            WHERE s.id = ?
        """, (seccion_id,)).fetchone()


def get_secciones_by_evento(evento_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute("""
            SELECT s.id, s.nombre, ts.nombre AS tipo,
                   s.ruta_archivo, s.texto_tts, s.duracion, s.creado_en,
                   s.regenerar_antes, es.orden, es.contabilizable
            FROM secciones s
            JOIN evento_secciones es ON es.seccion_id = s.id
            LEFT JOIN tipos_seccion ts ON ts.id = s.tipo_seccion_id
            WHERE es.evento_id = ?
            ORDER BY es.orden, s.id
        """, (evento_id,)).fetchall()


def set_contabilizable_en_evento(evento_id: int, seccion_id: int,
                                  value: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE evento_secciones SET contabilizable=? "
            "WHERE evento_id=? AND seccion_id=?",
            (value, evento_id, seccion_id)
        )
        conn.commit()


def get_secciones_disponibles_para_evento(evento_id: int) -> list[sqlite3.Row]:
    """Secciones NO asignadas aún a este evento."""
    with get_connection() as conn:
        return conn.execute("""
            SELECT s.id, s.nombre, ts.nombre AS tipo,
                   s.ruta_archivo, s.texto_tts, s.duracion
            FROM secciones s
            LEFT JOIN tipos_seccion ts ON ts.id = s.tipo_seccion_id
            WHERE s.id NOT IN (
                SELECT seccion_id FROM evento_secciones WHERE evento_id = ?
            )
            ORDER BY s.nombre
        """, (evento_id,)).fetchall()


def add_seccion_to_evento(evento_id: int, seccion_id: int) -> None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COALESCE(MAX(orden), 0) + 1 FROM evento_secciones WHERE evento_id=?",
            (evento_id,)
        ).fetchone()
        orden = row[0]
        conn.execute(
            "INSERT OR IGNORE INTO evento_secciones (evento_id, seccion_id, orden) VALUES (?,?,?)",
            (evento_id, seccion_id, orden)
        )
        conn.commit()


def remove_seccion_from_evento(evento_id: int, seccion_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM evento_secciones WHERE evento_id=? AND seccion_id=?",
            (evento_id, seccion_id)
        )
        conn.commit()


def move_seccion_in_evento(evento_id: int, seccion_id: int,
                            direction: int) -> None:
    """direction: -1 (arriba) o +1 (abajo)."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT seccion_id FROM evento_secciones WHERE evento_id=? ORDER BY orden",
            (evento_id,)
        ).fetchall()
        ids = [r["seccion_id"] for r in rows]
        if seccion_id not in ids:
            return
        idx = ids.index(seccion_id)
        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(ids):
            return
        ids[idx], ids[new_idx] = ids[new_idx], ids[idx]
        for i, sid in enumerate(ids):
            conn.execute(
                "UPDATE evento_secciones SET orden=? WHERE evento_id=? AND seccion_id=?",
                (i + 1, evento_id, sid)
            )
        conn.commit()


def delete_seccion(seccion_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM secciones WHERE id=?", (seccion_id,))
        conn.commit()


# ── programacion ───────────────────────────────────────────────────────────────
def insert_programacion(evento_id: int, fecha: str, hora: str,
                         recurrencia: str = "ninguna") -> int:
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM programacion WHERE evento_id=?", (evento_id,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE programacion SET fecha=?, hora=?, recurrencia=? WHERE evento_id=?",
                (fecha, hora, recurrencia, evento_id)
            )
            conn.commit()
            return existing["id"]
        c = conn.execute(
            "INSERT INTO programacion (evento_id, fecha, hora, recurrencia) VALUES (?,?,?,?)",
            (evento_id, fecha, hora, recurrencia)
        )
        conn.commit()
        return c.lastrowid


def get_all_programacion() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute("""
            SELECT p.id, p.evento_id, p.fecha, p.hora, p.recurrencia,
                   e.nombre AS evento_nombre, et.nombre AS evento_tipo
            FROM programacion p
            JOIN eventos e ON e.id = p.evento_id
            LEFT JOIN eventos_type et ON et.id = e.tipo_evento_id
            WHERE p.activo = 1
            ORDER BY p.fecha, p.hora
        """).fetchall()


def delete_programacion(prog_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM programacion WHERE id=?", (prog_id,))
        conn.commit()


def delete_programacion_by_evento(evento_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM programacion WHERE evento_id=?", (evento_id,))
        conn.commit()
