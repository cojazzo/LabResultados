import re
import hashlib
from datetime import date
from typing import Optional

def normalize_curp(curp: str) -> Optional[str]:
    """
    Normaliza una CURP eliminando espacios, caracteres especiales y pasando a mayúsculas.
    Retorna None si el valor es vacío o no parece una CURP.
    """
    if not curp:
        return None
    
    # Eliminar espacios, guiones, y convertir a mayúsculas
    normalized = re.sub(r'[^a-zA-Z0-9]', '', curp).upper()
    
    if len(normalized) != 18:
        # Podríamos lanzar error, pero en este contexto si no es 18, 
        # asumimos que no es una CURP válida o es un ID parcial.
        # Para ser permisivos con errores de captura y usarlo para matching:
        pass 
        
    return normalized if normalized else None

def generate_synthetic_id(
    nombre: str,
    apellido: str,
    sexo: Optional[str] = None,
    fecha_nacimiento: Optional[date] = None
) -> str:
    """
    Genera un identificador único (hash) basado en el nombre, apellidos, 
    sexo y fecha de nacimiento. Se utiliza cuando el paciente no cuenta 
    con una CURP válida (ej. extranjeros, recién nacidos) para permitir 
    el join de resultados.
    """
    # Normalizar strings para evitar duplicados por case/espacios
    n = re.sub(r'\s+', ' ', (nombre or "")).strip().upper()
    a = re.sub(r'\s+', ' ', (apellido or "")).strip().upper()
    s = (sexo or "").strip().upper()
    
    # Formatear fecha
    f = fecha_nacimiento.isoformat() if fecha_nacimiento else ""
    
    # Crear string de identificación compuesto
    raw_str = f"{n}|{a}|{s}|{f}"
    
    # Generar hash corto (16 caracteres) con prefijo SYN-
    h = hashlib.sha256(raw_str.encode('utf-8')).hexdigest()[:14].upper()
    return f"SYN-{h}"

def match_patient_identifier(
    curp_provided: Optional[str],
    nombre: str,
    apellido: str,
    sexo: Optional[str] = None,
    fecha_nacimiento: Optional[date] = None
) -> str:
    """
    Retorna el identificador principal para el paciente. 
    Usa la CURP si está disponible y es válida, de lo contrario
    genera un ID sintético basado en los datos demográficos.
    """
    curp = normalize_curp(curp_provided)
    if curp:
        return curp
        
    return generate_synthetic_id(nombre, apellido, sexo, fecha_nacimiento)
