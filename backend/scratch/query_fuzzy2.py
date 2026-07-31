import sqlite3
import difflib

conn = sqlite3.connect('lab_resultados.db')
cursor = conn.cursor()
cursor.execute("SELECT id, nombre, apellido, fecha_nacimiento FROM pacientes")
columns = [desc[0] for desc in cursor.description]
results = cursor.fetchall()
for row in results:
    r = dict(zip(columns, row))
    nombre_completo = f"{r['nombre']} {r['apellido']}".lower()
    
    # Check common misspellings
    if 'basur' in nombre_completo or 'vasul' in nombre_completo or 'vasur' in nombre_completo or 'basul' in nombre_completo:
        print(r)
