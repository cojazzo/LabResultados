import pandas as pd
from sqlalchemy import create_engine, text
import traceback

def main():
    engine_sqlite = create_engine("sqlite:///backend/lab_resultados.db")
    engine_pg = create_engine("postgresql+psycopg2://lab_user:lab_password_2026@localhost:5433/lab_resultados")

    # skip medicos as it's dropped in SQLite
    tables = [
        "usuarios", "quimicos", "pacientes", "pruebas",
        "lotes_carga", "resultados", "reportes_generados", 
        "reportes_resultados", "envios", "automation_events"
    ]

    for table in tables:
        print(f"Migrating {table}...")
        try:
            df = pd.read_sql_query(f"SELECT * FROM {table}", engine_sqlite)
            
            if df.empty:
                print(f"  Table {table} is empty.")
                continue
                
            # Cast booleans
            bool_cols = ['is_active', 'is_superuser', 'email_consent', 'whatsapp_consent', 'result_delivery_consent', 'activa']
            for col in bool_cols:
                if col in df.columns:
                    df[col] = df[col].astype(bool)
                    
            with engine_pg.begin() as pg_conn:
                pg_conn.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
                df.to_sql(table, pg_conn, if_exists='append', index=False)
                
                print(f"  Successfully migrated {len(df)} rows to {table}.")
                
                if 'id' in df.columns:
                    max_id = int(df['id'].max())
                    pg_conn.execute(text(f"SELECT setval('{table}_id_seq', {max_id})"))
                    
        except Exception as e:
            print(f"  Error migrating {table}: {e}")
            traceback.print_exc()

if __name__ == "__main__":
    main()
