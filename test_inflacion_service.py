import pytest
from datetime import date
from inflacion_service import parse_date, validate_llm_output
from config import MIN_DATE, MAX_DATE

def test_parse_date():
    assert parse_date("2020-01-01") == date(2020, 1, 1)
    
    with pytest.raises(ValueError):
        parse_date("01-01-2020")
        
def test_validate_llm_output_valid():
    data = {
        "fecha_inicio": "2020-01-01",
        "fecha_fin": "2021-01-01",
        "monto": 100.0,
        "is_valid": True,
        "respuesta_rechazo": ""
    }
    
    result = validate_llm_output(data)
    assert result["is_valid"] is True
    assert result["fecha_inicio"] == "2020-01-01"
    assert result["monto"] == 100.0
    
def test_validate_llm_output_missing_fields():
    data = {
        "fecha_inicio": "2020-01-01",
        "monto": 100.0,
        "is_valid": True,
        "respuesta_rechazo": ""
    }
    
    result = validate_llm_output(data)
    assert result["is_valid"] is False
    assert "Faltan campos" in result["respuesta_rechazo"]

def test_validate_llm_output_invalid_amount():
    data = {
        "fecha_inicio": "2020-01-01",
        "fecha_fin": "2021-01-01",
        "monto": -100.0,
        "is_valid": True,
        "respuesta_rechazo": ""
    }
    result = validate_llm_output(data)
    assert result["is_valid"] is False
    assert "El monto debe ser mayor a cero" in result["respuesta_rechazo"]

def test_validate_llm_output_invalid_date_range():
    data = {
        "fecha_inicio": "2021-01-01",
        "fecha_fin": "2020-01-01",
        "monto": 100.0,
        "is_valid": True,
        "respuesta_rechazo": ""
    }
    result = validate_llm_output(data)
    assert result["is_valid"] is False
    assert "La fecha de inicio no puede ser mayor a la fecha final" in result["respuesta_rechazo"]

def test_validate_llm_output_out_of_bounds_date():
    data = {
        "fecha_inicio": "2019-01-01",
        "fecha_fin": "2020-01-01",
        "monto": 100.0,
        "is_valid": True,
        "respuesta_rechazo": ""
    }
    result = validate_llm_output(data)
    assert result["is_valid"] is False
    assert "El rango permitido es de" in result["respuesta_rechazo"]

def test_validate_llm_output_valid_2026_date():
    data = {
        "fecha_inicio": "2026-01-01",
        "fecha_fin": "2026-02-01",
        "monto": 100.0,
        "is_valid": True,
        "respuesta_rechazo": ""
    }
    result = validate_llm_output(data)
    assert result["is_valid"] is True
    assert result["fecha_inicio"] == "2026-01-01"
    assert result["fecha_fin"] == "2026-02-01"

def test_validate_llm_output_invalid_future_date():
    data = {
        "fecha_inicio": "2026-01-01",
        "fecha_fin": "2026-03-01",
        "monto": 100.0,
        "is_valid": True,
        "respuesta_rechazo": ""
    }
    result = validate_llm_output(data)
    assert result["is_valid"] is False
    assert "El rango permitido es de" in result["respuesta_rechazo"]
