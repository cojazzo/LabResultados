import asyncio
import sqlite3
import asyncpg
import decimal

async def main():
    # Connect to SQLite
    sqlite_conn = sqlite3.connect("backend/lab_resultados.db")
    sqlite_conn.row_factory = sqlite3.Row
    cursor = sqlite_conn.cursor()

    # Connect to Postgres
    # Use 5433 which is the mapped port on the host
    pg_conn = await asyncpg.connect("postgresql://lab_user:lab_password_2026@localhost:5433/lab_resultados")

    # Order is important for foreign keys
    tables = [
        "usuarios", "medicos", "quimicos", "pacientes", "pruebas",
        "lotes_carga", "resultados", "reportes_generados", 
        "reportes_resultados", "envios", "automation_events"
    ]

    for table in tables:
        print(f"Migrating table {table}...")
        try:
            cursor.execute(f"SELECT * FROM {table}")
            rows = cursor.fetchall()
            if not rows:
                print(f"  No rows in {table}.")
                continue
                
            columns = rows[0].keys()
            
            # Clear table in postgres
            await pg_conn.execute(f"TRUNCATE TABLE {table} CASCADE")

            # Prepare insert query
            query = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(['$' + str(i+1) for i in range(len(columns))])})"
            
            # Extract values, handling any type conversions if necessary
            values = []
            for row in rows:
                row_vals = []
                for col in columns:
                    val = row[col]
                    row_vals.append(val)
                values.append(tuple(row_vals))
            
            await pg_conn.executemany(query, values)
            print(f"  Successfully migrated {len(rows)} rows to {table}.")
            
            # Fix auto-increment sequence
            try:
                await pg_conn.execute(f"SELECT setval('{table}_id_seq', COALESCE((SELECT MAX(id) FROM {table}), 1))")
            except Exception as seq_e:
                pass # some tables might not have an id_seq

        except Exception as e:
            print(f"  Error migrating {table}: {e}")

    await pg_conn.close()
    sqlite_conn.close()
    print("Migration complete!")

if __name__ == "__main__":
    asyncio.run(main())
