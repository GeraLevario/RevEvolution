
import sqlite3
from pathlib import Path

# Base de datos del proyecto.
DB_PATH = Path(__file__).resolve().parent / "repevolution.db"


def conectar():
    conexion = sqlite3.connect(DB_PATH)
    conexion.row_factory = sqlite3.Row
    conexion.execute("PRAGMA foreign_keys = ON")
    return conexion


def inicializar_db():
    with conectar() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                correo TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_hash TEXT NOT NULL,
                creado_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS rutinas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                dia_semana TEXT NOT NULL,
                objetivo TEXT,
                activa INTEGER NOT NULL DEFAULT 1,
                creada_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS ejercicios_rutina (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rutina_id INTEGER NOT NULL,
                nombre TEXT NOT NULL,
                orden INTEGER NOT NULL DEFAULT 1,
                series_objetivo INTEGER NOT NULL DEFAULT 3,
                repeticiones_objetivo INTEGER NOT NULL DEFAULT 10,
                FOREIGN KEY (rutina_id)
                    REFERENCES rutinas(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS sesiones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rutina_id INTEGER,
                nombre_rutina TEXT NOT NULL,
                dia_semana TEXT NOT NULL,
                fecha TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                estado TEXT NOT NULL DEFAULT 'en_progreso',
                FOREIGN KEY (rutina_id)
                    REFERENCES rutinas(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS ejercicios_sesion (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sesion_id INTEGER NOT NULL,
                nombre TEXT NOT NULL,
                orden INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (sesion_id)
                    REFERENCES sesiones(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS series (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ejercicio_sesion_id INTEGER NOT NULL,
                numero_serie INTEGER NOT NULL,
                peso_kg REAL NOT NULL DEFAULT 0,
                repeticiones INTEGER NOT NULL DEFAULT 0,
                completada INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (ejercicio_sesion_id)
                    REFERENCES ejercicios_sesion(id) ON DELETE CASCADE
            );


             CREATE TABLE IF NOT EXISTS biblioteca_ejercicios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL COLLATE NOCASE UNIQUE,
                grupo_muscular TEXT NOT NULL,
                equipamiento TEXT NOT NULL DEFAULT 'Ninguno',
                instrucciones TEXT NOT NULL DEFAULT '',
                imagen_url TEXT NOT NULL DEFAULT '',
                gif_url TEXT NOT NULL DEFAULT '',
                creado_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );








        """)

        # Añadir la relación con el usuario sin eliminar datos existentes.
        columnas_rutinas = {
            columna["name"]
            for columna in db.execute(
                "PRAGMA table_info(rutinas)"
            ).fetchall()
        }

        if "usuario_id" not in columnas_rutinas:
            db.execute("""
                ALTER TABLE rutinas
                ADD COLUMN usuario_id INTEGER
                REFERENCES usuarios(id) ON DELETE CASCADE
            """)



        # Guardar también el peso inicial de cada ejercicio de la rutina.
        columnas_ejercicios = {
            columna["name"]
            for columna in db.execute(
                "PRAGMA table_info(ejercicios_rutina)"
            ).fetchall()
        }

        if "peso_objetivo" not in columnas_ejercicios:
            db.execute("""
                ALTER TABLE ejercicios_rutina
                ADD COLUMN peso_objetivo REAL NOT NULL DEFAULT 0
            """)

        # Evitar que una cuenta tenga dos rutinas para el mismo día.
        db.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_rutinas_usuario_dia
            ON rutinas(usuario_id, dia_semana)
            WHERE usuario_id IS NOT NULL
        """)




        columnas_sesiones = {
            columna["name"]
            for columna in db.execute(
                "PRAGMA table_info(sesiones)"
            ).fetchall()
        }

        if "usuario_id" not in columnas_sesiones:
            db.execute("""
                ALTER TABLE sesiones
                ADD COLUMN usuario_id INTEGER
                REFERENCES usuarios(id) ON DELETE CASCADE

                
            """)


if __name__ == "__main__":
    inicializar_db()
    print(f"Base de datos preparada en: {DB_PATH}")
