from datetime import date
import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import api.main as api_main
import copilot_api_service
import inflacion_service
from api.main import app


client = TestClient(app)


def _successful_copilot_output():
    return {
        "pregunta": "¿A cuánto equivalen 100 pesos de 2020 a 2024?",
        "intencion": {
            "is_valid": True,
            "respuesta_rechazo": "",
            "fecha_inicio": "2020-01-01",
            "fecha_fin": "2024-01-01",
            "monto": 100.0,
        },
        "resultado": {
            "ok": True,
            "mensaje": "Cálculo realizado correctamente.",
            "detalle": {
                "fecha_inicio": "2020-01-01",
                "fecha_fin": "2024-01-01",
                "monto_inicial": 100.0,
                "monto_actualizado": 125.0,
                "inflacion_pct": 25.0,
                "factor_actualizacion": 1.25,
                "inpc_inicio": 100.0,
                "inpc_fin": 125.0,
            },
        },
        "historico": pd.DataFrame(
            {
                "Fecha": pd.to_datetime(["2024-01-01", "2020-01-01"]),
                "INPC": [125.0, 100.0],
            }
        ),
        "texto_resultado": "Resultado formateado",
        "comentario_analitico": "El poder adquisitivo disminuyó en el periodo.",
    }


def test_copilot_query_returns_json_serializable_conversational_result(monkeypatch):
    calls = []

    def fake_process(question):
        calls.append(question)
        return _successful_copilot_output()

    monkeypatch.setattr(inflacion_service, "procesar_pregunta_inflacion", fake_process)

    response = client.post(
        "/copilot/query",
        json={"question": "  ¿A cuánto equivalen 100 pesos de 2020 a 2024?  "},
    )

    assert response.status_code == 200
    body = response.json()
    assert calls == ["¿A cuánto equivalen 100 pesos de 2020 a 2024?"]
    assert body["question"] == calls[0]
    assert body["intent"]["monto"] == 100.0
    assert body["result"]["detalle"]["monto_actualizado"] == 125.0
    assert body["history"] == [
        {"date": "2020-01-01T00:00:00", "inpc": 100.0},
        {"date": "2024-01-01T00:00:00", "inpc": 125.0},
    ]
    assert body["formatted_result"] == "Resultado formateado"
    assert body["analytical_comment"] == (
        "El poder adquisitivo disminuyó en el periodo."
    )
    json.dumps(body)


def test_copilot_query_rejects_blank_question_without_calling_service(monkeypatch):
    def unexpected_call(*_args, **_kwargs):
        raise AssertionError("The conversational service must not be called")

    monkeypatch.setattr(
        inflacion_service, "procesar_pregunta_inflacion", unexpected_call
    )

    response = client.post("/copilot/query", json={"question": "   "})

    assert response.status_code == 400
    assert response.json() == {"detail": "La pregunta es obligatoria."}


def test_copilot_query_preserves_controlled_domain_rejection(monkeypatch):
    output = _successful_copilot_output()
    output["intencion"] = {
        "is_valid": False,
        "respuesta_rechazo": "Solo puedo responder sobre inflación en México.",
        "fecha_inicio": None,
        "fecha_fin": None,
        "monto": None,
    }
    output["resultado"] = {
        "ok": False,
        "mensaje": "Consulta no válida.",
        "detalle": None,
    }
    monkeypatch.setattr(
        inflacion_service, "procesar_pregunta_inflacion", lambda *_: output
    )

    response = client.post("/copilot/query", json={"question": "¿Quién ganó?"})

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Solo puedo responder sobre inflación en México."
    }


@pytest.mark.parametrize(
    "sensitive_message",
    [
        "Error al interpretar la consulta: token secreto de Vertex",
        "La respuesta del modelo no fue un JSON válido.",
    ],
)
def test_copilot_query_does_not_expose_gemini_internal_errors(
    monkeypatch, sensitive_message
):
    output = _successful_copilot_output()
    output["intencion"] = {
        "is_valid": False,
        "respuesta_rechazo": sensitive_message,
        "fecha_inicio": None,
        "fecha_fin": None,
        "monto": None,
    }
    monkeypatch.setattr(
        inflacion_service, "procesar_pregunta_inflacion", lambda *_: output
    )

    response = client.post("/copilot/query", json={"question": "Consulta"})

    assert response.status_code == 502
    assert response.json() == {
        "detail": "No se pudo interpretar la consulta en este momento."
    }
    assert "secreto" not in response.text
    assert "JSON" not in response.text


def test_copilot_query_does_not_expose_bigquery_internal_errors(monkeypatch):
    output = _successful_copilot_output()
    output["resultado"] = {
        "ok": False,
        "mensaje": "❌ Error al calcular equivalencia por inflación: credencial privada",
        "detalle": None,
    }
    monkeypatch.setattr(
        inflacion_service, "procesar_pregunta_inflacion", lambda *_: output
    )

    response = client.post("/copilot/query", json={"question": "Consulta"})

    assert response.status_code == 502
    assert response.json() == {
        "detail": "No se pudo calcular la equivalencia en este momento."
    }
    assert "credencial privada" not in response.text


def test_copilot_query_sanitizes_optional_comment_failure(monkeypatch):
    output = _successful_copilot_output()
    output["comentario_analitico"] = (
        "No se pudo generar el análisis analítico: endpoint privado de Vertex"
    )
    monkeypatch.setattr(
        inflacion_service, "procesar_pregunta_inflacion", lambda *_: output
    )

    response = client.post("/copilot/query", json={"question": "Consulta"})

    assert response.status_code == 200
    assert response.json()["analytical_comment"] == (
        "No se pudo generar el análisis analítico."
    )
    assert "endpoint privado" not in response.text


def test_copilot_history_returns_ordered_serializable_values(monkeypatch):
    monkeypatch.setattr(
        inflacion_service, "obtener_max_fecha_bq", lambda: date(2026, 2, 1)
    )
    monkeypatch.setattr(
        inflacion_service,
        "obtener_historico_inpc",
        lambda *_: pd.DataFrame(
            {
                "Fecha": [date(2020, 3, 1), date(2020, 1, 1), date(2020, 2, 1)],
                "INPC": [106.0, 104.0, 105.0],
            }
        ),
    )

    response = client.get(
        "/copilot/history?start_date=2020-01-01&end_date=2020-03-01"
    )

    assert response.status_code == 200
    assert response.json() == {
        "start_date": "2020-01-01",
        "end_date": "2020-03-01",
        "indicator": "INPC - General",
        "source": "INEGI / BigQuery",
        "history": [
            {"date": "2020-01-01", "inpc": 104.0},
            {"date": "2020-02-01", "inpc": 105.0},
            {"date": "2020-03-01", "inpc": 106.0},
        ],
    }


def test_copilot_history_validates_date_range_before_querying_history(monkeypatch):
    monkeypatch.setattr(
        inflacion_service, "obtener_max_fecha_bq", lambda: date(2026, 2, 1)
    )

    def unexpected_history(*_args, **_kwargs):
        raise AssertionError("History must not be queried for an invalid range")

    monkeypatch.setattr(
        inflacion_service, "obtener_historico_inpc", unexpected_history
    )

    response = client.get(
        "/copilot/history?start_date=2024-01-01&end_date=2020-01-01"
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "start_date no puede ser mayor que end_date."
    }


def test_copilot_history_does_not_expose_bigquery_exception(monkeypatch):
    monkeypatch.setattr(
        inflacion_service, "obtener_max_fecha_bq", lambda: date(2026, 2, 1)
    )

    def failing_history(*_args, **_kwargs):
        raise RuntimeError("dataset-secreto.tabla-privada")

    monkeypatch.setattr(inflacion_service, "obtener_historico_inpc", failing_history)

    response = client.get(
        "/copilot/history?start_date=2020-01-01&end_date=2020-03-01"
    )

    assert response.status_code == 502
    assert response.json() == {
        "detail": "No se pudo obtener el historico de INPC en este momento."
    }
    assert "dataset-secreto" not in response.text


def test_copilot_date_range_returns_available_boundaries(monkeypatch):
    monkeypatch.setattr(
        inflacion_service, "obtener_max_fecha_bq", lambda: date(2026, 6, 1)
    )

    response = client.get("/copilot/date-range")

    assert response.status_code == 200
    assert response.json() == {
        "min_date": "2000-01-01",
        "max_date": "2026-06-01",
        "indicator": "INPC - General",
        "source": "INEGI / BigQuery",
    }


def test_copilot_date_range_does_not_expose_internal_exception(monkeypatch):
    def failing_date_range():
        raise RuntimeError("credencial secreta")

    monkeypatch.setattr(inflacion_service, "obtener_max_fecha_bq", failing_date_range)

    response = client.get("/copilot/date-range")

    assert response.status_code == 502
    assert response.json() == {
        "detail": "No se pudo obtener el rango de fechas en este momento."
    }
    assert "credencial secreta" not in response.text


def test_existing_deterministic_endpoints_never_invoke_gemini(monkeypatch):
    def forbidden_gemini_call():
        raise AssertionError("Gemini must not be used by deterministic endpoints")

    monkeypatch.setattr(inflacion_service, "get_gemini_model", forbidden_gemini_call)

    period_result = {
        "start_date": "2020-01-01",
        "end_date": "2024-01-01",
        "inpc_start": 100.0,
        "inpc_end": 125.0,
        "factor": 1.25,
        "inflation_pct": 25.0,
        "source": "INEGI / BigQuery",
        "indicator": "INPC - General",
        "method": "inflation_pct = ((inpc_end / inpc_start) - 1) * 100",
    }
    average_result = {
        "contract": "average-period-unchanged",
    }
    monthly_result = {
        "contract": "monthly-comparable-unchanged",
    }
    monkeypatch.setattr(api_main, "calculate_inflation_period", lambda **_: period_result)
    monkeypatch.setattr(
        api_main, "calculate_average_period_inflation", lambda **_: average_result
    )
    monkeypatch.setattr(
        api_main, "calculate_monthly_comparable_inflation", lambda **_: monthly_result
    )

    health = client.get("/health")
    period = client.get(
        "/inflation/period?start_date=2020-01-01&end_date=2024-01-01"
    )
    average = client.get(
        "/inflation/average-period?current_year=2025&previous_year=2024&month_limit=12"
    )
    monthly = client.get(
        "/inflation/monthly-comparable?current_year=2025&previous_year=2024&month_limit=12"
    )

    assert health.status_code == 200
    assert health.json() == {
        "status": "ok",
        "service": "inflacion-copilot-api",
    }
    assert period.status_code == 200
    assert period.json() == period_result
    assert average.status_code == 200
    assert average.json() == average_result
    assert monthly.status_code == 200
    assert monthly.json() == monthly_result


def test_copilot_service_rejects_non_dataframe_history():
    with pytest.raises(
        copilot_api_service.CopilotDependencyError,
        match="No se pudo obtener el historico de INPC",
    ):
        copilot_api_service.serialize_history([{"Fecha": "2020-01-01", "INPC": 100}])
