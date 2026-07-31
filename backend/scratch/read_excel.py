import pandas as pd
import sys

file_path = r"C:\Users\Emerson.Collazo\Downloads\2207-270726.xls"
try:
    df = pd.read_excel(file_path)
    # Find any row where any column contains "basulto" (case insensitive)
    mask = df.apply(lambda row: row.astype(str).str.contains('basulto', case=False, na=False).any(), axis=1)
    basulto_rows = df[mask]
    
    if basulto_rows.empty:
        print("No se encontró 'basulto' en el archivo.")
    else:
        for index, row in basulto_rows.iterrows():
            print("=== Fila encontrada ===")
            for col in df.columns:
                print(f"{col}: {row[col]}")
except Exception as e:
    print(f"Error reading excel: {e}")
