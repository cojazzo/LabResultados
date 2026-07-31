import sqlite3
conn = sqlite3.connect('lab_resultados.db')
cursor = conn.cursor()
cursor.execute("SELECT id, nombre, apellido, fecha_nacimiento FROM pacientes")
columns = [desc[0] for desc in cursor.description]
results = cursor.fetchall()
for row in results:
    r = dict(zip(columns, row))
    if 'basulto' in r['nombre'].lower() or 'basulto' in r['apellido'].lower():
        print(r)
