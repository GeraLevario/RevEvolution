
import os
import sqlite3
from functools import wraps

from flask import (
    Flask, render_template, request, jsonify,
    redirect, url_for, session, flash
)
from werkzeug.security import generate_password_hash, check_password_hash

from database import inicializar_db, conectar
from ejercicios_iniciales import cargar_ejercicios

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "FLASK_SECRET_KEY",
    "cambia-esta-clave-antes-de-publicar-repevolution"
)

inicializar_db()
cargar_ejercicios()



# ---------- AUTENTICACIÓN ----------

def usuario_requerido_api(funcion):
    @wraps(funcion)
    def envoltura(*args, **kwargs):
        if "usuario_id" not in session:
            return jsonify({
                "error": "Inicia sesión para continuar."
            }), 401
        return funcion(*args, **kwargs)
    return envoltura


@app.route("/")
def inicio():
    return render_template("index.html")

@app.route("/registro", methods=["GET", "POST"])
def registro():
    if "usuario_id" in session:
        return redirect(url_for("entrenamiento"))

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        correo = request.form.get("correo", "").strip().lower()
        password = request.form.get("password", "")
        confirmar = request.form.get("confirmar_password", "")

        if not nombre or not correo or not password or not confirmar:
            flash("Completa todos los campos.")
            return render_template("registro.html")

        if len(nombre) > 100 or len(correo) > 254:
            flash("El nombre o correo es demasiado largo.")
            return render_template("registro.html")

        if "@" not in correo or "." not in correo.rsplit("@", 1)[-1]:
            flash("Introduce un correo válido.")
            return render_template("registro.html")

        if len(password) < 8:
            flash("La contraseña debe tener al menos 8 caracteres.")
            return render_template("registro.html")

        if password != confirmar:
            flash("Las contraseñas no coinciden.")
            return render_template("registro.html")

        password_hash = generate_password_hash(password)

        try:
            with conectar() as db:
                cursor = db.execute(
                    """
                    INSERT INTO usuarios (nombre, correo, password_hash)
                    VALUES (?, ?, ?)
                    """,
                    (nombre, correo, password_hash)
                )
                nuevo_usuario_id = cursor.lastrowid

            session.clear()
            session["usuario_id"] = nuevo_usuario_id
            session["usuario_nombre"] = nombre

            return redirect(url_for("entrenamiento"))

        except sqlite3.IntegrityError:
            flash("Ese correo ya tiene una cuenta.")
        except Exception:
            app.logger.exception("Error al registrar usuario")
            flash("No se pudo crear la cuenta. Inténtalo de nuevo.")

    return render_template("registro.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if "usuario_id" in session:
        return redirect(url_for("entrenamiento"))

    if request.method == "POST":
        correo = request.form.get("correo", "").strip().lower()
        password = request.form.get("password", "")

        with conectar() as db:
            usuario = db.execute(
                """
                SELECT id, nombre, correo, password_hash
                FROM usuarios
                WHERE correo = ?
                """,
                (correo,)
            ).fetchone()

        if usuario and check_password_hash(
            usuario["password_hash"], password
        ):
            session.clear()
            session["usuario_id"] = usuario["id"]
            session["usuario_nombre"] = usuario["nombre"]
            return redirect(url_for("entrenamiento"))

        flash("Correo o contraseña incorrectos.")

    return render_template("login.html")



@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("inicio"))




@app.route("/entrenamiento")
def entrenamiento():
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    return render_template("entrenamiento.html")




@app.route("/historial")
@usuario_requerido_api
def pagina_historial():
    return render_template("historial.html")

@app.route("/historial/<int:sesion_id>")
@usuario_requerido_api
def pagina_detalle_historial(sesion_id):
    return render_template(
        "detalle_historial.html",
        sesion_id=sesion_id
    )


# ---------- VALIDACIÓN Y GUARDADO DE ENTRENAMIENTOS ----------

def validar_datos(datos):
    if not isinstance(datos, dict):
        raise ValueError("Datos inválidos.")

    nombre = str(datos.get("nombre", "")).strip()
    dia = str(datos.get("dia", "")).strip()
    ejercicios = datos.get("ejercicios")

    if not nombre or not dia or not isinstance(ejercicios, list):
        raise ValueError("Faltan datos de la sesión.")

    for ejercicio in ejercicios:
        if not isinstance(ejercicio, dict):
            raise ValueError("Ejercicio inválido.")

        if not str(ejercicio.get("nombre", "")).strip():
            raise ValueError("Falta el nombre de un ejercicio.")

        series = ejercicio.get("series")
        if not isinstance(series, list) or not series:
            raise ValueError("Cada ejercicio debe tener series.")

        for serie in series:
            if not isinstance(serie, dict):
                raise ValueError("Serie inválida.")

            peso = float(serie.get("peso", 0))
            reps = int(serie.get("repeticiones", 0))

            if peso < 0 or reps < 0:
                raise ValueError("Peso o repeticiones inválidos.")

    return nombre, dia, ejercicios


def guardar_ejercicios(db, sesion_id, ejercicios):
    db.execute(
        "DELETE FROM ejercicios_sesion WHERE sesion_id = ?",
        (sesion_id,)
    )

    for orden, ejercicio in enumerate(ejercicios, start=1):
        cursor = db.execute(
            """
            INSERT INTO ejercicios_sesion (sesion_id, nombre, orden)
            VALUES (?, ?, ?)
            """,
            (sesion_id, ejercicio["nombre"].strip(), orden)
        )
        ejercicio_id = cursor.lastrowid

        for numero, serie in enumerate(ejercicio["series"], start=1):
            peso = float(serie.get("peso", 0))
            reps = int(serie.get("repeticiones", 0))
            completada = 1 if serie.get("completada") else 0

            db.execute(
                """
                INSERT INTO series
                    (ejercicio_sesion_id, numero_serie,
                     peso_kg, repeticiones, completada)
                VALUES (?, ?, ?, ?, ?)
                """,
                (ejercicio_id, numero, peso, reps, completada)
            )



# ---------- API DE RUTINAS SEMANALES ----------   /GL

DIAS_SEMANA = (
    "Lunes", "Martes", "Miércoles", "Jueves",
    "Viernes", "Sábado", "Domingo"
)


@app.route("/api/rutinas", methods=["GET"])
@usuario_requerido_api
def consultar_rutinas():
    usuario_id = session["usuario_id"]

    with conectar() as db:
        rutinas = db.execute(
            """
            SELECT id, nombre, dia_semana, objetivo
            FROM rutinas
            WHERE usuario_id = ? AND activa = 1
            ORDER BY CASE dia_semana
                WHEN 'Lunes' THEN 1
                WHEN 'Martes' THEN 2
                WHEN 'Miércoles' THEN 3
                WHEN 'Jueves' THEN 4
                WHEN 'Viernes' THEN 5
                WHEN 'Sábado' THEN 6
                WHEN 'Domingo' THEN 7
                ELSE 8
            END
            """,
            (usuario_id,)
        ).fetchall()

        resultado = []

        for rutina in rutinas:
            ejercicios = db.execute(
                """
                SELECT nombre, orden, series_objetivo,
                       repeticiones_objetivo, peso_objetivo
                FROM ejercicios_rutina
                WHERE rutina_id = ?
                ORDER BY orden
                """,
                (rutina["id"],)
            ).fetchall()

            resultado.append({
                "id": rutina["id"],
                "nombre": rutina["nombre"],
                "dia": rutina["dia_semana"],
                "objetivo": rutina["objetivo"] or "",
                "ejercicios": [
                    {
                        "nombre": e["nombre"],
                        "series": e["series_objetivo"],
                        "repeticiones": e["repeticiones_objetivo"],
                        "peso_kg": e["peso_objetivo"]
                    }
                    for e in ejercicios
                ]
            })

    return jsonify({"rutinas": resultado})


@app.route("/api/rutinas/<string:dia>", methods=["GET"])
@usuario_requerido_api


def consultar_rutina_dia(dia):
    if dia not in DIAS_SEMANA:
        return jsonify({"error": "Día de la semana inválido."}), 400

    usuario_id = session["usuario_id"]

    with conectar() as db:
        rutina = db.execute(
            """
            SELECT id, nombre, dia_semana, objetivo
            FROM rutinas
            WHERE usuario_id = ? AND dia_semana = ? AND activa = 1
            LIMIT 1
            """,
            (usuario_id, dia)
        ).fetchone()

        if rutina is None:
            return jsonify({"rutina": None})

        ejercicios = db.execute(
            """
            SELECT nombre, orden, series_objetivo,
                   repeticiones_objetivo, peso_objetivo
            FROM ejercicios_rutina
            WHERE rutina_id = ?
            ORDER BY orden
            """,
            (rutina["id"],)
        ).fetchall()

    return jsonify({
        "rutina": {
            "id": rutina["id"],
            "nombre": rutina["nombre"],
            "dia": rutina["dia_semana"],
            "objetivo": rutina["objetivo"] or "",
            "ejercicios": [
                {
                    "nombre": e["nombre"],
                    "series": e["series_objetivo"],
                    "repeticiones": e["repeticiones_objetivo"],
                    "peso_kg": e["peso_objetivo"]
                }
                for e in ejercicios
            ]
        }
    })


@app.route("/api/rutinas", methods=["POST"])
@usuario_requerido_api
def guardar_rutina():
    datos = request.get_json(silent=True)

    if not isinstance(datos, dict):
        return jsonify({"error": "Los datos de la rutina no son válidos."}), 400

    nombre = str(datos.get("nombre", "")).strip()
    dia = str(datos.get("dia", "")).strip()
    objetivo = str(datos.get("objetivo", "")).strip()
    ejercicios = datos.get("ejercicios")

    if not nombre or len(nombre) > 120:
        return jsonify({"error": "Escribe un nombre válido para la rutina."}), 400

    if dia not in DIAS_SEMANA:
        return jsonify({"error": "Selecciona un día válido."}), 400

    if len(objetivo) > 200:
        return jsonify({"error": "El objetivo es demasiado largo."}), 400

    if not isinstance(ejercicios, list) or not ejercicios:
        return jsonify({"error": "Agrega al menos un ejercicio."}), 400

    if len(ejercicios) > 50:
        return jsonify({"error": "La rutina no puede superar 50 ejercicios."}), 400

    ejercicios_validados = []

    try:
        for ejercicio in ejercicios:
            if not isinstance(ejercicio, dict):
                raise ValueError("Hay un ejercicio inválido.")

            nombre_ejercicio = str(ejercicio.get("nombre", "")).strip()
            series = int(ejercicio.get("series", 0))
            repeticiones = int(ejercicio.get("repeticiones", 0))
            peso = float(ejercicio.get("peso_kg", 0))

            if not nombre_ejercicio or len(nombre_ejercicio) > 120:
                raise ValueError("Cada ejercicio necesita un nombre válido.")

            if not 1 <= series <= 30:
                raise ValueError("Las series deben estar entre 1 y 30.")

            if not 1 <= repeticiones <= 500:
                raise ValueError("Las repeticiones deben estar entre 1 y 500.")

            if not 0 <= peso <= 1000 or not __import__("math").isfinite(peso):
                raise ValueError("Revisa el peso inicial de los ejercicios.")

            ejercicios_validados.append({
                "nombre": nombre_ejercicio,
                "series": series,
                "repeticiones": repeticiones,
                "peso": peso
            })

    except (ValueError, TypeError, OverflowError):
        return jsonify({
            "error": "Revisa los nombres, series, repeticiones y pesos."
        }), 400

    usuario_id = session["usuario_id"]

    try:
        with conectar() as db:
            existente = db.execute(
                """
                SELECT id
                FROM rutinas
                WHERE usuario_id = ? AND dia_semana = ?
                LIMIT 1
                """,
                (usuario_id, dia)
            ).fetchone()

            if existente:
                rutina_id = existente["id"]

                db.execute(
                    """
                    UPDATE rutinas
                    SET nombre = ?, objetivo = ?, activa = 1
                    WHERE id = ? AND usuario_id = ?
                    """,
                    (nombre, objetivo, rutina_id, usuario_id)
                )

                db.execute(
                    "DELETE FROM ejercicios_rutina WHERE rutina_id = ?",
                    (rutina_id,)
                )
            else:
                cursor = db.execute(
                    """
                    INSERT INTO rutinas
                        (usuario_id, nombre, dia_semana, objetivo, activa)
                    VALUES (?, ?, ?, ?, 1)
                    """,
                    (usuario_id, nombre, dia, objetivo)
                )
                rutina_id = cursor.lastrowid

            for orden, ejercicio in enumerate(ejercicios_validados, start=1):
                db.execute(
                    """
                    INSERT INTO ejercicios_rutina
                        (rutina_id, nombre, orden, series_objetivo,
                         repeticiones_objetivo, peso_objetivo)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        rutina_id,
                        ejercicio["nombre"],
                        orden,
                        ejercicio["series"],
                        ejercicio["repeticiones"],
                        ejercicio["peso"]
                    )
                )

        return jsonify({
            "mensaje": "Rutina guardada correctamente.",
            "rutina_id": rutina_id,
            "dia": dia
        }), 200

    except Exception:
        app.logger.exception("Error al guardar la rutina")
        return jsonify({
            "error": "No se pudo guardar la rutina."
        }), 500



@app.route("/api/rutinas/configuracion", methods=["POST"])
@usuario_requerido_api


def guardar_configuracion_rutina():
    datos = request.get_json(silent=True)

    if not isinstance(datos, dict):
        return jsonify({"error": "Configuración inválida."}), 400

    dia = str(datos.get("dia", "")).strip()
    nombre = str(datos.get("nombre", "")).strip() or "Mi entrenamiento"
    objetivo = str(datos.get("objetivo", "")).strip()

    if dia not in DIAS_SEMANA:
        return jsonify({"error": "Selecciona un día válido."}), 400

    if len(nombre) > 120 or len(objetivo) > 200:
        return jsonify({"error": "Revisa el nombre y el objetivo."}), 400

    usuario_id = session["usuario_id"]

    try:
        with conectar() as db:
            existente = db.execute(
                """
                SELECT id FROM rutinas
                WHERE usuario_id = ? AND dia_semana = ?
                LIMIT 1
                """,
                (usuario_id, dia)
            ).fetchone()

            if existente:
                db.execute(
                    """
                    UPDATE rutinas
                    SET nombre = ?, objetivo = ?, activa = 1
                    WHERE id = ? AND usuario_id = ?
                    """,
                    (nombre, objetivo, existente["id"], usuario_id)
                )
            else:
                db.execute(
                    """
                    INSERT INTO rutinas
                        (usuario_id, nombre, dia_semana, objetivo, activa)
                    VALUES (?, ?, ?, ?, 1)
                    """,
                    (usuario_id, nombre, dia, objetivo)
                )

        return jsonify({"mensaje": "Configuración guardada."}), 200

    except Exception:
        app.logger.exception("Error al guardar la configuración de rutina")
        return jsonify({"error": "No se pudo guardar la configuración."}), 500


@app.route("/api/rutinas/<int:rutina_id>", methods=["DELETE"])
@usuario_requerido_api
def eliminar_rutina(rutina_id):
    usuario_id = session["usuario_id"]

    try:
        with conectar() as db:
            rutina = db.execute(
                """
                SELECT id
                FROM rutinas
                WHERE id = ? AND usuario_id = ? AND activa = 1
                """,
                (rutina_id, usuario_id)
            ).fetchone()

            if rutina is None:
                return jsonify({
                    "error": "No se encontró la rutina."
                }), 404

            # Desactivar la rutina para conservar sus relaciones
            # y evitar borrar el historial de entrenamientos.
            db.execute(
                """
                UPDATE rutinas
                SET activa = 0
                WHERE id = ? AND usuario_id = ?
                """,
                (rutina_id, usuario_id)
            )

        return jsonify({
            "mensaje": "Rutina eliminada correctamente."
        }), 200

    except Exception:
        app.logger.exception("Error al eliminar la rutina")
        return jsonify({
            "error": "No se pudo eliminar la rutina."
        }), 500



# ---------- API: ELIMINAR UNA SESIÓN DEL HISTORIAL ----------

@app.route("/api/historial/<int:sesion_id>", methods=["DELETE"])
@usuario_requerido_api
def eliminar_sesion_historial(sesion_id):
    usuario_id = session["usuario_id"]

    try:
        with conectar() as db:
            sesion = db.execute(
                """
                SELECT id
                FROM sesiones
                WHERE id = ? AND usuario_id = ?
                """,
                (sesion_id, usuario_id)
            ).fetchone()

            if sesion is None:
                return jsonify({
                    "error": "No se encontró el entrenamiento."
                }), 404

            db.execute(
                """
                DELETE FROM sesiones
                WHERE id = ? AND usuario_id = ?
                """,
                (sesion_id, usuario_id)
            )

        return jsonify({
            "mensaje": "Entrenamiento eliminado correctamente."
        }), 200

    except Exception:
        app.logger.exception("Error al eliminar el entrenamiento")
        return jsonify({
            "error": "No se pudo eliminar el entrenamiento."
        }), 500





# ---------- API DE SESIONES: DATOS DEL USUARIO ACTUAL ----------

@app.route("/api/sesiones/activa", methods=["GET"])
@usuario_requerido_api
def consultar_sesion_activa():
    usuario_id = session["usuario_id"]

    with conectar() as db:
        sesion = db.execute(
            """
            SELECT *
            FROM sesiones
            WHERE usuario_id = ? AND estado = 'en_progreso'
            ORDER BY id DESC
            LIMIT 1
            """,
            (usuario_id,)
        ).fetchone()

        if sesion is None:
            return jsonify({"sesion": None, "ejercicios": []})

        ejercicios = db.execute(
            """
            SELECT id, nombre, orden
            FROM ejercicios_sesion
            WHERE sesion_id = ?
            ORDER BY orden
            """,
            (sesion["id"],)
        ).fetchall()

        resultado = []

        for ejercicio in ejercicios:
            series = db.execute(
                """
                SELECT numero_serie, peso_kg, repeticiones, completada
                FROM series
                WHERE ejercicio_sesion_id = ?
                ORDER BY numero_serie
                """,
                (ejercicio["id"],)
            ).fetchall()

            resultado.append({
                "nombre": ejercicio["nombre"],
                "series": [dict(serie) for serie in series]
            })

    return jsonify({
        "sesion": dict(sesion),
        "ejercicios": resultado
    })


@app.route("/api/sesiones", methods=["POST"])
@usuario_requerido_api
def crear_sesion():
    try:
        nombre, dia, ejercicios = validar_datos(
            request.get_json(silent=True)
        )

        usuario_id = session["usuario_id"]

        with conectar() as db:
            cursor = db.execute(
                """
                INSERT INTO sesiones
                    (usuario_id, nombre_rutina, dia_semana, estado)
                VALUES (?, ?, ?, 'en_progreso')
                """,
                (usuario_id, nombre, dia)
            )
            sesion_id = cursor.lastrowid
            guardar_ejercicios(db, sesion_id, ejercicios)

        return jsonify({
            "mensaje": "Entrenamiento guardado.",
            "sesion_id": sesion_id
        }), 201

    except (ValueError, TypeError, OverflowError) as error:
        return jsonify({"error": str(error)}), 400
    except Exception:
        app.logger.exception("Error al crear la sesión")
        return jsonify({
            "error": "No se pudo guardar el entrenamiento."
        }), 500




# ---------- API: DETALLE DE UNA SESIÓN DEL HISTORIAL ----------

@app.route("/api/historial/<int:sesion_id>", methods=["GET"])
@usuario_requerido_api
def consultar_detalle_historial(sesion_id):
    usuario_id = session["usuario_id"]

    with conectar() as db:
        sesion = db.execute(
            """
            SELECT *
            FROM sesiones
            WHERE id = ? AND usuario_id = ?
            """,
            (sesion_id, usuario_id)
        ).fetchone()

        if sesion is None:
            return jsonify({
                "error": "Entrenamiento no encontrado."
            }), 404

        ejercicios = db.execute(
            """
            SELECT id, nombre, orden
            FROM ejercicios_sesion
            WHERE sesion_id = ?
            ORDER BY orden
            """,
            (sesion_id,)
        ).fetchall()

        resultado = []

        for ejercicio in ejercicios:
            series = db.execute(
                """
                SELECT numero_serie, peso_kg, repeticiones, completada
                FROM series
                WHERE ejercicio_sesion_id = ?
                ORDER BY numero_serie
                """,
                (ejercicio["id"],)
            ).fetchall()

            resultado.append({
                "nombre": ejercicio["nombre"],
                "series": [dict(serie) for serie in series]
            })

    return jsonify({
        "sesion": dict(sesion),
        "ejercicios": resultado
    })






@app.route("/api/sesiones/<int:sesion_id>", methods=["PUT"])
@usuario_requerido_api
def actualizar_sesion(sesion_id):
    datos = request.get_json(silent=True) or {}

    try:
        nombre, dia, ejercicios = validar_datos(datos)
        estado = datos.get("estado", "en_progreso")
        usuario_id = session["usuario_id"]

        if estado not in ("en_progreso", "finalizado"):
            return jsonify({"error": "Estado inválido."}), 400

        with conectar() as db:
            existente = db.execute(
                """
                SELECT id FROM sesiones
                WHERE id = ? AND usuario_id = ?
                """,
                (sesion_id, usuario_id)
            ).fetchone()

            if existente is None:
                return jsonify({
                    "error": "Entrenamiento no encontrado."
                }), 404

            db.execute(
                """
                UPDATE sesiones
                SET nombre_rutina = ?, dia_semana = ?, estado = ?
                WHERE id = ? AND usuario_id = ?
                """,
                (nombre, dia, estado, sesion_id, usuario_id)
            )

            guardar_ejercicios(db, sesion_id, ejercicios)

        return jsonify({"mensaje": "Entrenamiento actualizado."})

    except (ValueError, TypeError, OverflowError) as error:
        return jsonify({"error": str(error)}), 400
    except Exception:
        app.logger.exception("Error al actualizar la sesión")
        return jsonify({
            "error": "No se pudo actualizar el entrenamiento."
        }), 500



@app.route("/api/historial", methods=["GET"])
@usuario_requerido_api
def obtener_historial():
    usuario_id = session["usuario_id"]

    with conectar() as db:
        sesiones = db.execute(
            """
            SELECT *
            FROM sesiones
            WHERE usuario_id = ?
            ORDER BY id DESC
            """,
            (usuario_id,)
        ).fetchall()

    return jsonify({
        "sesiones": [dict(sesion) for sesion in sesiones]
    })




@app.route("/api/sesiones/<int:sesion_id>", methods=["GET"])
@usuario_requerido_api
def consultar_sesion(sesion_id):
    usuario_id = session["usuario_id"]

    with conectar() as db:
        sesion = db.execute(
            """
            SELECT * FROM sesiones
            WHERE id = ? AND usuario_id = ?
            """,
            (sesion_id, usuario_id)
        ).fetchone()

        if sesion is None:
            return jsonify({
                "error": "Entrenamiento no encontrado."
            }), 404

        ejercicios = db.execute(
            """
            SELECT id, nombre, orden
            FROM ejercicios_sesion
            WHERE sesion_id = ?
            ORDER BY orden
            """,
            (sesion_id,)
        ).fetchall()

        resultado = []

        for ejercicio in ejercicios:
            series = db.execute(
                """
                SELECT numero_serie, peso_kg, repeticiones, completada
                FROM series
                WHERE ejercicio_sesion_id = ?
                ORDER BY numero_serie
                """,
                (ejercicio["id"],)
            ).fetchall()

            resultado.append({
                "nombre": ejercicio["nombre"],
                "series": [dict(serie) for serie in series]
            })

    return jsonify({
        "sesion": dict(sesion),
        "ejercicios": resultado
    })


@app.route("/api/biblioteca-ejercicios", methods=["GET"])
@usuario_requerido_api
def obtener_biblioteca_ejercicios():
    with conectar() as db:
        ejercicios = db.execute("""
            SELECT
                id,
                nombre,
                grupo_muscular,
                equipamiento,
                instrucciones,
                imagen_url,
                gif_url
            FROM biblioteca_ejercicios
            ORDER BY grupo_muscular, nombre
        """).fetchall()

    return jsonify({
        "ejercicios": [dict(ejercicio) for ejercicio in ejercicios]
    })




if __name__ == "__main__":
    app.run(debug=True)
