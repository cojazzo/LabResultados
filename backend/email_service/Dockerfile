FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código del servidor
COPY ews_email_server.py .

# Exponer el puerto
EXPOSE 8765

# Comando para ejecutar el servidor (asegurando que escuche en todas las interfaces)
CMD ["python", "-c", "import uvicorn; import ews_email_server; uvicorn.run(ews_email_server.app, host='0.0.0.0', port=8765, log_level='info')"]
