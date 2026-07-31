import sqlite3
conn = sqlite3.connect('lab_resultados.db')
cursor = conn.cursor()
cursor.execute("SELECT id, nombre, apellido, fecha_nacimiento FROM pacientes WHERE fecha_nacimiento LIKE '2055%'")
columns = [desc[0] for desc in cursor.description]
for row in cursor.fetchall():
    print(dict(zip(columns, row)))
