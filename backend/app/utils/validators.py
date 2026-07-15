import re
from datetime import date, datetime

def normalize_column_name(name: str) -> str:
    """Normaliza nombres de columna: minúsculas, sin espacios, sin guiones."""
    if not isinstance(name, str):
        return ""
    # Strip, lower, replace spaces and hyphens with underscores
    name_clean = name.strip().lower().replace(" ", "_").replace("-", "_")
    # Remove accents/diacritics if any (simplified)
    replacements = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'ü': 'u', 'ñ': 'n'
    }
    for orig, rep in replacements.items():
        name_clean = name_clean.replace(orig, rep)
    return name_clean

def validate_email(email: str) -> bool:
    """Validación básica de formato de email."""
    if not email:
        return False
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))

def validate_phone(phone: str) -> bool:
    """Validación de formato de teléfono (números con opcional + al inicio, de 10 a 15 dígitos)."""
    if not phone:
        return False
    pattern = r"^\+?[0-9]{10,15}$"
    return bool(re.match(pattern, phone.strip().replace(" ", "")))

def parse_date(date_val) -> date | None:
    """Parsea fechas en múltiples formatos."""
    if isinstance(date_val, date):
        return date_val
    if isinstance(date_val, datetime):
        return date_val.date()
    if not isinstance(date_val, str):
        return None
    
    date_str = date_val.strip()
    if not date_str:
        return None

    formats = [
        "%Y-%m-%d",      # 2026-07-10
        "%d/%m/%Y",      # 10/07/2026
        "%d/%m/%y",      # 10/07/26 (2-digit year)
        "%m/%d/%Y",      # 07/10/2026
        "%m/%d/%y",      # 07/10/26 (2-digit year)
        "%d-%m-%Y",      # 10-07-2026
        "%d-%m-%y",      # 10-07-26 (2-digit year)
        "%Y/%m/%d",      # 2026/07/10
        "%d.%m.%Y",      # 10.07.2026
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None

def calcular_interpretacion(
    valor: float,
    valor_min: float,
    valor_max: float,
    valor_critico_min: float | None = None,
    valor_critico_max: float | None = None,
) -> str:
    """Calcula la interpretación de un resultado de laboratorio."""
    try:
        val = float(valor)
    except (ValueError, TypeError):
        return "normal"  # Fallback for text results

    if valor_critico_min is not None and val < float(valor_critico_min):
        return "critico_bajo"
    if valor_critico_max is not None and val > float(valor_critico_max):
        return "critico_alto"
    
    # Check if min/max exist
    val_min = float(valor_min) if valor_min is not None else None
    val_max = float(valor_max) if valor_max is not None else None

    if val_min is not None and val < val_min:
        return "bajo"
    if val_max is not None and val > val_max:
        return "alto"
    
    return "normal"
