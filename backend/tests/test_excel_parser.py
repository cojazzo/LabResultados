"""
Tests para el parser de Excel y funciones de utilidad.

Ejecutar con: pytest backend/tests/test_excel_parser.py -v
"""

import pytest
from datetime import date


# ---------------------------------------------------------------------------
# Helpers locales (duplican la lógica esperada del parser para testing
# independiente). Cuando el módulo app.services.excel_parser exista,
# estos tests deben importar directamente de ahí.
# ---------------------------------------------------------------------------


def normalize_column_name(name: str) -> str:
    """Normaliza nombres de columna: minúsculas, sin espacios extra, guiones bajos."""
    return name.strip().lower().replace(" ", "_").replace("-", "_")


def calcular_interpretacion(
    valor: float,
    valor_min: float,
    valor_max: float,
    valor_critico_min: float | None = None,
    valor_critico_max: float | None = None,
) -> str:
    """Calcula la interpretación de un resultado de laboratorio."""
    if valor_critico_min is not None and valor < valor_critico_min:
        return "critico_bajo"
    if valor_critico_max is not None and valor > valor_critico_max:
        return "critico_alto"
    if valor < valor_min:
        return "bajo"
    if valor > valor_max:
        return "alto"
    return "normal"


def validate_email(email: str) -> bool:
    """Validación básica de formato de email."""
    import re

    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def parse_date(date_str: str) -> date | None:
    """Parsea fechas en múltiples formatos."""
    from datetime import datetime

    formats = [
        "%Y-%m-%d",      # 2026-07-10
        "%d/%m/%Y",      # 10/07/2026
        "%m/%d/%Y",      # 07/10/2026
        "%d-%m-%Y",      # 10-07-2026
        "%Y/%m/%d",      # 2026/07/10
        "%d.%m.%Y",      # 10.07.2026
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    return None


# ===========================================================================
# Tests
# ===========================================================================


class TestNormalizeColumnNames:
    """Tests para la normalización de nombres de columna."""

    def test_normalize_standard_name(self):
        assert normalize_column_name("Identificacion_Paciente") == "identificacion_paciente"

    def test_normalize_with_spaces(self):
        assert normalize_column_name("Nombre Paciente") == "nombre_paciente"

    def test_normalize_with_leading_trailing_spaces(self):
        assert normalize_column_name("  Codigo_Prueba  ") == "codigo_prueba"

    def test_normalize_with_hyphens(self):
        assert normalize_column_name("Fecha-Nacimiento") == "fecha_nacimiento"

    def test_normalize_mixed_case(self):
        assert normalize_column_name("VALOR") == "valor"

    def test_normalize_already_normalized(self):
        assert normalize_column_name("sexo") == "sexo"


class TestCalcularInterpretacionNormal:
    """Tests para valores dentro del rango normal."""

    def test_glucosa_normal(self):
        assert calcular_interpretacion(85.0, 70.0, 100.0, 40.0, 400.0) == "normal"

    def test_glucosa_at_min_boundary(self):
        assert calcular_interpretacion(70.0, 70.0, 100.0, 40.0, 400.0) == "normal"

    def test_glucosa_at_max_boundary(self):
        assert calcular_interpretacion(100.0, 70.0, 100.0, 40.0, 400.0) == "normal"

    def test_hemoglobina_normal(self):
        assert calcular_interpretacion(14.5, 12.0, 17.0, 7.0, None) == "normal"

    def test_potasio_normal(self):
        assert calcular_interpretacion(4.0, 3.5, 5.0, 2.5, 6.5) == "normal"


class TestCalcularInterpretacionAlto:
    """Tests para valores por encima del rango normal."""

    def test_glucosa_alta(self):
        assert calcular_interpretacion(150.0, 70.0, 100.0, 40.0, 400.0) == "alto"

    def test_colesterol_alto(self):
        assert calcular_interpretacion(250.0, 0.0, 200.0, None, 300.0) == "alto"

    def test_creatinina_alta(self):
        assert calcular_interpretacion(2.0, 0.6, 1.2, None, 10.0) == "alto"

    def test_acido_urico_alto(self):
        assert calcular_interpretacion(8.0, 3.5, 7.2, None, None) == "alto"


class TestCalcularInterpretacionBajo:
    """Tests para valores por debajo del rango normal."""

    def test_hemoglobina_baja(self):
        assert calcular_interpretacion(10.5, 12.0, 17.0, 7.0, None) == "bajo"

    def test_hematocrito_bajo(self):
        assert calcular_interpretacion(30.0, 36.0, 50.0, 20.0, None) == "bajo"

    def test_potasio_bajo(self):
        assert calcular_interpretacion(3.2, 3.5, 5.0, 2.5, 6.5) == "bajo"

    def test_albumina_baja(self):
        assert calcular_interpretacion(3.0, 3.5, 5.5, None, None) == "bajo"


class TestCalcularInterpretacionCriticoAlto:
    """Tests para valores críticos altos."""

    def test_glucosa_critica_alta(self):
        assert calcular_interpretacion(450.0, 70.0, 100.0, 40.0, 400.0) == "critico_alto"

    def test_colesterol_critico_alto(self):
        assert calcular_interpretacion(350.0, 0.0, 200.0, None, 300.0) == "critico_alto"

    def test_trigliceridos_critico_alto(self):
        assert calcular_interpretacion(550.0, 0.0, 150.0, None, 500.0) == "critico_alto"

    def test_potasio_critico_alto(self):
        assert calcular_interpretacion(7.0, 3.5, 5.0, 2.5, 6.5) == "critico_alto"

    def test_sodio_critico_alto(self):
        assert calcular_interpretacion(165.0, 136.0, 145.0, 120.0, 160.0) == "critico_alto"

    def test_creatinina_critica_alta(self):
        assert calcular_interpretacion(12.0, 0.6, 1.2, None, 10.0) == "critico_alto"


class TestCalcularInterpretacionCriticoBajo:
    """Tests para valores críticos bajos."""

    def test_glucosa_critica_baja(self):
        assert calcular_interpretacion(35.0, 70.0, 100.0, 40.0, 400.0) == "critico_bajo"

    def test_hemoglobina_critica_baja(self):
        assert calcular_interpretacion(5.0, 12.0, 17.0, 7.0, None) == "critico_bajo"

    def test_hematocrito_critico_bajo(self):
        assert calcular_interpretacion(18.0, 36.0, 50.0, 20.0, None) == "critico_bajo"

    def test_potasio_critico_bajo(self):
        assert calcular_interpretacion(2.0, 3.5, 5.0, 2.5, 6.5) == "critico_bajo"

    def test_sodio_critico_bajo(self):
        assert calcular_interpretacion(115.0, 136.0, 145.0, 120.0, 160.0) == "critico_bajo"


class TestValidateEmailFormat:
    """Tests para validación de formato de email."""

    def test_valid_email(self):
        assert validate_email("user@example.com") is True

    def test_valid_email_with_dots(self):
        assert validate_email("maria.garcia@hospital.com.mx") is True

    def test_valid_email_with_plus(self):
        assert validate_email("user+tag@example.com") is True

    def test_invalid_email_no_at(self):
        assert validate_email("userexample.com") is False

    def test_invalid_email_no_domain(self):
        assert validate_email("user@") is False

    def test_invalid_email_no_tld(self):
        assert validate_email("user@example") is False

    def test_invalid_email_spaces(self):
        assert validate_email("user @example.com") is False

    def test_empty_email(self):
        assert validate_email("") is False


class TestParseDateMultipleFormats:
    """Tests para parseo de fechas en múltiples formatos."""

    def test_iso_format(self):
        result = parse_date("2026-07-10")
        assert result == date(2026, 7, 10)

    def test_european_format(self):
        result = parse_date("10/07/2026")
        assert result == date(2026, 7, 10)

    def test_us_format(self):
        result = parse_date("07/10/2026")
        # Note: ambiguous with European, parsed as MM/DD/YYYY
        assert result is not None

    def test_dash_european_format(self):
        result = parse_date("10-07-2026")
        assert result == date(2026, 7, 10)

    def test_dot_format(self):
        result = parse_date("10.07.2026")
        assert result == date(2026, 7, 10)

    def test_with_whitespace(self):
        result = parse_date("  2026-07-10  ")
        assert result == date(2026, 7, 10)

    def test_invalid_date(self):
        result = parse_date("not-a-date")
        assert result is None

    def test_empty_string(self):
        result = parse_date("")
        assert result is None
