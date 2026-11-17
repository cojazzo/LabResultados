"""
Catálogo de campos del Examen General de Orina (EGO).

Estudios, unidades y valores de referencia tomados del "Formato de registro de estudios de
laboratorio INAER". Es la única definición: la usan la API (validación y respuesta), la pantalla
de captura (vía /api/ego/campos) y el PDF.

`sugerencias` son opciones frecuentes para autocompletar en la captura; el químico puede escribir
cualquier otro valor. No se usan para interpretar resultados.
"""

FISICO = "fisico"
QUIMICO = "quimico"
MICROSCOPICO = "microscopico"

SECCIONES = [
    (FISICO, "Examen físico"),
    (QUIMICO, "Examen químico"),
    (MICROSCOPICO, "Examen microscópico"),
]

_NEG = ["Negativo", "Trazas", "+", "++", "+++"]

CAMPOS = [
    # clave, estudio, sección, unidades, referencia, sugerencias
    ("color", "Color", FISICO, "", "Amarillo", ["Amarillo", "Amarillo claro", "Amarillo intenso", "Ámbar", "Incoloro", "Rojizo"]),
    ("aspecto", "Aspecto", FISICO, "", "Transparente", ["Transparente", "Ligeramente turbio", "Turbio"]),

    ("glucosa", "Glucosa", QUIMICO, "mg/dL", "Negativo", _NEG),
    ("bilirrubina", "Bilirrubinas", QUIMICO, "mg/dL", "Negativo", _NEG),
    ("cetonas", "Cetonas", QUIMICO, "mg/dL", "Negativo", _NEG),
    ("densidad", "G.E. (gravedad específica)", QUIMICO, "", "1.005 – 1.025", []),
    ("sangre", "Sangre", QUIMICO, "Eri/µL", "Negativo", _NEG),
    ("ph", "pH", QUIMICO, "", "5.0 – 8.0", []),
    ("proteinas", "Proteínas", QUIMICO, "mg/dL", "Negativo", _NEG),
    ("urobilinogeno", "Urobilinógeno", QUIMICO, "mg/dL", "0.2 – 1.0", ["Normal"]),
    ("nitritos", "Nitritos", QUIMICO, "", "Negativo", ["Negativo", "Positivo"]),
    ("leucocitos_esterasa", "Leucocitos (esterasa leucocitaria)", QUIMICO, "Leu/µL", "Negativo", _NEG),

    ("bacterias", "Bacterias", MICROSCOPICO, "", "", ["Escasas", "Moderadas", "Abundantes"]),
    ("celulas_epiteliales", "Células epiteliales", MICROSCOPICO, "", "Escasas", ["Escasas", "Moderadas", "Abundantes"]),
    ("leucocitos_campo", "Leucocitos", MICROSCOPICO, "CPA", "0 – 2 / CPA", []),
    ("sedimento", "Sedimento observado en campo alto", MICROSCOPICO, "CPA", "", []),
]

CLAVES = [c[0] for c in CAMPOS]
CLAVES_QUIMICO = [c[0] for c in CAMPOS if c[2] == QUIMICO]


def campos_como_dict() -> list[dict]:
    return [
        {"clave": k, "estudio": e, "seccion": s, "unidades": u, "referencia": r, "sugerencias": sug}
        for k, e, s, u, r, sug in CAMPOS
    ]
