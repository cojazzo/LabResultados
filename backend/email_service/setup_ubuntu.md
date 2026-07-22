# Instalación de EWS Email Service en Ubuntu (Systemd)

Sigue estos pasos en tu servidor Ubuntu para desplegar el microservicio de envíos EWS como un servicio nativo (`systemd`).

## 1. Preparar el entorno

Clona o copia la carpeta `backend/email_service` a tu servidor, por ejemplo en `/opt/labresultados/email_service`.

```bash
sudo mkdir -p /opt/labresultados
sudo cp -r email_service /opt/labresultados/
cd /opt/labresultados/email_service
```

## 2. Instalar dependencias

Es recomendable usar un entorno virtual de Python.

```bash
sudo apt update
sudo apt install python3-venv python3-pip -y

# Crear entorno virtual
python3 -m venv venv

# Instalar dependencias
./venv/bin/pip install -r requirements.txt
```

## 3. Configurar variables de entorno

Crea el archivo `.env` con las credenciales:

```bash
cat << 'EOF' > .env
EWS_USERNAME=gobags\inaer.resultados
EWS_PASSWORD=TU_CONTRASEÑA_AQUI
EWS_EMAIL=inaer.resultados@aguascalientes.gob.mx
EWS_URL=https://autodiscover.aguascalientes.gob.mx/EWS/Exchange.asmx
EWS_API_KEY=UN_TOKEN_SEGURO_GENERADO_POR_TI
EOF

chmod 600 .env
```

*(Recuerda editar el archivo `.env` y colocar la contraseña real y generar una API Key segura).*

## 4. Crear el servicio Systemd

Crea el archivo de servicio para que se ejecute en segundo plano y se inicie automáticamente:

```bash
sudo nano /etc/systemd/system/ews_email.service
```

Pega el siguiente contenido:

```ini
[Unit]
Description=EWS Email Service para LabResultados
After=network.target

[Service]
User=root
WorkingDirectory=/opt/labresultados/email_service
EnvironmentFile=/opt/labresultados/email_service/.env
ExecStart=/opt/labresultados/email_service/venv/bin/python ews_email_server.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

## 5. Iniciar y habilitar el servicio

```bash
sudo systemctl daemon-reload
sudo systemctl enable ews_email.service
sudo systemctl start ews_email.service
```

## 6. Verificar el estado

```bash
sudo systemctl status ews_email.service
```

Debería decir `active (running)`. Puedes ver los logs en tiempo real con:

```bash
sudo journalctl -u ews_email.service -f
```

## 7. Prueba rápida

```bash
curl http://127.0.0.1:8765/health
```
Debe devolver `{"status":"ok", ...}`
