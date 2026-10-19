
from database import conectar


EJERCICIOS = [
    # PECHO
    ("Press de banca con barra", "Pecho", "Barra",
     "Baja la barra con control hacia el pecho y empuja hasta extender los brazos."),
    ("Press inclinado con mancuernas", "Pecho", "Mancuernas",
     "Mantén el banco inclinado, baja las mancuernas controladamente y empuja hacia arriba."),
    ("Aperturas con mancuernas", "Pecho", "Mancuernas",
     "Con una ligera flexión de codos, abre y cierra los brazos de forma controlada."),
    ("Cruce de poleas", "Pecho", "Poleas",
     "Lleva las manos al frente sin balancear el cuerpo."),

    # ESPALDA
    ("Jalón al pecho", "Espalda", "Polea",
     "Lleva la barra hacia la parte superior del pecho sin balancearte."),
    ("Remo sentado", "Espalda", "Polea",
     "Tira del agarre hacia el torso manteniendo la espalda estable."),
    ("Remo con mancuerna", "Espalda", "Mancuernas",
     "Apoya una mano, mantén la espalda estable y lleva la mancuerna hacia la cadera."),
    ("Dominadas", "Espalda", "Peso corporal",
     "Eleva el cuerpo hacia la barra sin impulsarte con balanceos."),

    # PIERNA
    ("Sentadilla con barra", "Pierna", "Barra",
     "Desciende manteniendo el control, el tronco estable y los pies apoyados."),
    ("Prensa de piernas", "Pierna", "Máquina",
     "Baja la plataforma controladamente y evita bloquear las rodillas al extender."),
    ("Extensión de cuádriceps", "Pierna", "Máquina",
     "Extiende las rodillas de forma controlada y baja el peso lentamente."),
    ("Curl femoral", "Pierna", "Máquina",
     "Flexiona las rodillas sin levantar la cadera del apoyo."),

    # HOMBROS
    ("Press de hombros con mancuernas", "Hombros", "Mancuernas",
     "Empuja las mancuernas hacia arriba sin arquear excesivamente la espalda."),
    ("Elevaciones laterales", "Hombros", "Mancuernas",
     "Eleva los brazos hacia los lados con los codos ligeramente flexionados."),
    ("Face pull", "Hombros", "Polea",
     "Lleva la cuerda hacia el rostro manteniendo los codos abiertos."),

    # BÍCEPS
    ("Curl de bíceps con barra", "Bíceps", "Barra",
     "Flexiona los codos sin balancear el torso."),
    ("Curl martillo", "Bíceps", "Mancuernas",
     "Sube las mancuernas con las palmas enfrentadas y controla el descenso."),

    # TRÍCEPS
    ("Extensión de tríceps en polea", "Tríceps", "Polea",
     "Extiende los codos manteniéndolos cerca del torso."),
    ("Extensión de tríceps por encima de la cabeza", "Tríceps", "Mancuerna",
     "Extiende los brazos sobre la cabeza sin forzar la zona lumbar."),

    # ABDOMEN
    ("Plancha abdominal", "Abdomen", "Peso corporal",
     "Mantén el cuerpo alineado y contrae el abdomen sin hundir la cadera."),
    ("Crunch abdominal", "Abdomen", "Peso corporal",
     "Eleva ligeramente el torso mediante la contracción abdominal, sin tirar del cuello."),
]


def cargar_ejercicios():
    with conectar() as db:
        for nombre, grupo, equipo, instrucciones in EJERCICIOS:
            db.execute(
                """
                INSERT INTO biblioteca_ejercicios
                    (nombre, grupo_muscular, equipamiento, instrucciones)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(nombre) DO NOTHING
                """,
                (nombre, grupo, equipo, instrucciones),
            )


if __name__ == "__main__":
    cargar_ejercicios()
    print(f"Catálogo preparado: {len(EJERCICIOS)} ejercicios iniciales.")
