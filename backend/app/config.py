from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
import os

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./lab_resultados.db"
    SECRET_KEY: str = "your-secret-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    SYSTEM_API_KEY: str = "sys_98f6d3b4a2e1c5798a7b6c5d4e3f2a1b"

    # Configuración del Laboratorio
    LAB_NAME: str = "Laboratorio Clínico"
    LAB_ADDRESS: str = "Av. Gómez Morín S/N Col. la Estación C.P. 20180, Aguascalientes, Ags. Fideicomiso complejo Tres Centurias (a un costado del CHMH)"
    LAB_PHONE: str = "449 459 57 97"
    LAB_EMAIL: str = "contacto@laboratorio.com"

    # Email (SMTP)
    MAIL_USERNAME: str = "your-email@example.com"
    MAIL_PASSWORD: str = "your-app-password"
    MAIL_FROM: str = "resultados@labsanrafael.com"
    MAIL_PORT: int = 587
    MAIL_SERVER: str = "smtp.example.com"
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False
    MAIL_USE_CREDENTIALS: bool = True

    # Integración con n8n
    N8N_WEBHOOK_URL: str = "http://n8n:5678/webhook/enviar-resultados"
    N8N_WEBHOOK_SECRET: str = "n8n-webhook-secret-key-change-this"
    N8N_OUTLOOK_WEBHOOK_URL: str = "http://n8n:5678/webhook/enviar-resultados"
    N8N_OUTLOOK_WEBHOOK_SECRET: str = "wh_a7f938b2c4e6d5a1f09e8d7c6b5a4f3e"

    # Twilio (WhatsApp) - DEPRECATED en backend (se mueve a n8n)
    TWILIO_ACCOUNT_SID: str = "your-twilio-sid"
    TWILIO_AUTH_TOKEN: str = "your-twilio-token"
    TWILIO_WHATSAPP_FROM: str = "whatsapp:+14155238886"

    # App Settings
    BASE_URL: str = "http://localhost:8000"
    PDF_STORAGE_PATH: str = "./storage/pdfs"
    MOCK_EMAIL: bool = True
    MOCK_WHATSAPP: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

@lru_cache
def get_settings() -> Settings:
    return Settings()
