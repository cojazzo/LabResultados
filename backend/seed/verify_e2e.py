import asyncio
import httpx
import sys
import os
from pathlib import Path

# Add root directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE_URL = "http://127.0.0.1:8000/api"

async def run_e2e_verification():
    print("🚀 Iniciando verificación E2E del backend API...")

    async with httpx.AsyncClient() as client:
        # 1. Login
        print("\n🔑 1. Intentando iniciar sesión...")
        login_data = {
            "username": "admin",
            "password": "admin123"
        }
        # FastAPI OAuth2PasswordRequestForm uses form-encoded data
        response = await client.post(f"{BASE_URL}/auth/login", data=login_data)
        if response.status_code != 200:
            print(f"❌ Error al iniciar sesión: {response.status_code} - {response.text}")
            return
        
        token_data = response.json()
        token = token_data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("✅ Sesión iniciada con éxito. Token JWT obtenido.")

        # 2. Cargar Excel
        print("\n📊 2. Cargando archivo Excel de resultados...")
        excel_path = Path(__file__).parent / "ejemplo_resultados_corregido.xlsx"
        if not excel_path.exists():
            print(f"❌ Archivo Excel no encontrado en {excel_path}")
            return
            
        with open(excel_path, "rb") as f:
            files = {"files": (excel_path.name, f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            response = await client.post(f"{BASE_URL}/upload/excel", files=files, headers=headers)
            
        if response.status_code != 200:
            print(f"❌ Error al subir Excel: {response.status_code} - {response.text}")
            return
            
        upload_data = response.json()
        print("✅ Archivo Excel cargado exitosamente.")
        lote = upload_data["lotes"][0]
        print(f"   Lote ID: {lote['id']}")
        print(f"   Filas exitosas: {lote['registros_exitosos']}")
        print(f"   Filas con error: {lote['registros_error']}")
        
        lote_id = lote["id"]

        # 3. Obtener resultados
        print("\n🔍 3. Verificando resultados guardados en base de datos...")
        response = await client.get(f"{BASE_URL}/resultados?limit=10", headers=headers)
        if response.status_code != 200:
            print(f"❌ Error al obtener resultados: {response.status_code} - {response.text}")
            return
            
        resultados_data = response.json()
        total_resultados = len(resultados_data)
        print(f"✅ Resultados obtenidos. Total en base de datos: {total_resultados}")
        if total_resultados == 0:
            print("❌ No se encontraron resultados guardados.")
            return
            
        # Tomar los resultados del primer paciente para generar el reporte
        primer_resultado = resultados_data[0]
        paciente_id = primer_resultado["paciente"]["id"]
        paciente_nombre = f"{primer_resultado['paciente']['nombre']} {primer_resultado['paciente']['apellido']}"
        print(f"   Paciente seleccionado para reporte: {paciente_nombre} (ID: {paciente_id})")

        # Buscar todos los resultados de este paciente
        response = await client.get(f"{BASE_URL}/resultados?paciente_id={paciente_id}", headers=headers)
        res_paciente = response.json()
        resultado_ids = [r["id"] for r in res_paciente]
        print(f"   Resultados del paciente para incluir: {resultado_ids}")

        # 4. Generar reporte PDF
        print("\n📄 4. Generando reporte PDF...")
        reporte_req = {
            "paciente_id": paciente_id,
            "resultado_ids": resultado_ids,
            "lote_carga_id": lote_id
        }
        response = await client.post(f"{BASE_URL}/reportes/generar", json=reporte_req, headers=headers)
        if response.status_code != 200:
            print(f"❌ Error al generar reporte: {response.status_code} - {response.text}")
            return
            
        reporte_data = response.json()
        reporte_id = reporte_data["id"]
        folio = reporte_data["folio"]
        print(f"✅ Reporte PDF generado exitosamente.")
        print(f"   Folio: {folio}")
        print(f"   ID Reporte: {reporte_id}")

        # 5. Enviar reporte por email
        print("\n📧 5. Enviando reporte por correo electrónico (Mock)...")
        email_req = {
            "reporte_id": reporte_id,
            "destinatario_email": "paciente.test@email.com",
            "copia_medico": False
        }
        response = await client.post(f"{BASE_URL}/envios/email", json=email_req, headers=headers)
        if response.status_code != 200:
            print(f"❌ Error al enviar email: {response.status_code} - {response.text}")
            return
            
        envio_data = response.json()
        envio_id = envio_data["id"]
        print(f"✅ Correo registrado y en proceso.")
        print(f"   ID Envío: {envio_id}")
        print(f"   Destinatario: {envio_data['destinatario']}")
        print(f"   Estado Inicial: {envio_data['estado']}")

        # 6. Verificar historial de envíos
        print("\n📊 6. Verificando historial de envíos...")
        response = await client.get(f"{BASE_URL}/envios", headers=headers)
        if response.status_code != 200:
            print(f"❌ Error al obtener envíos: {response.status_code} - {response.text}")
            return
            
        envios_data = response.json()
        envio_final = next((e for e in envios_data if e["id"] == envio_id), None)
        if not envio_final:
            print("❌ El envío no se encuentra en el historial.")
            return
            
        print(f"✅ Envío localizado en historial.")
        print(f"   Canal: {envio_final['canal']}")
        print(f"   Destinatario: {envio_final['destinatario']}")
        print(f"   Estado Final: {envio_final['estado']}")
        
        # 7. Resumen de Dashboard
        print("\n📈 7. Verificando KPIs del Dashboard...")
        response = await client.get(f"{BASE_URL}/dashboard/resumen", headers=headers)
        if response.status_code != 200:
            print(f"❌ Error al obtener resumen de dashboard: {response.status_code} - {response.text}")
            return
            
        dash_data = response.json()
        print(f"✅ KPIs obtenidos del Dashboard:")
        print(f"   Total Pruebas: {dash_data['total_pruebas']}")
        print(f"   Total Pacientes: {dash_data['total_pacientes']}")
        print(f"   Valores Fuera de Rango: {dash_data['porcentaje_fuera_rango']}%")
        print(f"   Total Reportes: {dash_data['total_reportes']}")
        print(f"   Envíos Exitosos: {dash_data['total_envios_exitosos']}")

        print("\n🎉 ¡VERIFICACIÓN E2E COMPLETADA CON ÉXITO! 🎉")

if __name__ == "__main__":
    asyncio.run(run_e2e_verification())
