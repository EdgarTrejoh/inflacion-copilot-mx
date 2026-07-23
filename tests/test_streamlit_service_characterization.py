from datetime import date

import pandas as pd
import pytest

import inflacion_service as service


class FakeGeminiResponse:
    def __init__(self, text):
        self.text = text


class FakeGeminiModel:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def generate_content(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        if self.error:
            raise self.error
        return FakeGeminiResponse(self.response)


class FakeQueryJob:
    def __init__(self, rows=None, dataframe=None):
        self._rows = rows or []
        self._dataframe = dataframe

    def result(self):
        return self._rows

    def to_dataframe(self):
        return self._dataframe.copy()


class FakeBigQueryClient:
    def __init__(self, job=None, error=None):
        self.job = job
        self.error = error
        self.calls = []

    def query(self, query, job_config=None):
        self.calls.append((query, job_config))
        if self.error:
            raise self.error
        return self.job


@pytest.fixture
def fixed_available_range(monkeypatch):
    monkeypatch.setattr(service, "obtener_max_fecha_bq", lambda: date(2026, 2, 1))


def test_valid_inflation_query_is_extracted_and_validated(monkeypatch, fixed_available_range):
    model = FakeGeminiModel(
        '{"fecha_inicio":"2020-01-01","fecha_fin":"2024-01-01",'
        '"monto":1000,"is_valid":true,"respuesta_rechazo":""}'
    )
    monkeypatch.setattr(service, "get_gemini_model", lambda: model)

    result = service.clasificar_consulta_inflacion(
        "¿A cuánto equivalen 1,000 pesos de enero de 2020 a enero de 2024?"
    )

    assert result == {
        "is_valid": True,
        "respuesta_rechazo": "",
        "fecha_inicio": "2020-01-01",
        "fecha_fin": "2024-01-01",
        "monto": 1000.0,
    }
    assert "generation_config" in model.calls[0][1]


def test_out_of_domain_query_preserves_gemini_rejection(monkeypatch, fixed_available_range):
    model = FakeGeminiModel(
        '{"fecha_inicio":null,"fecha_fin":null,"monto":null,'
        '"is_valid":false,"respuesta_rechazo":"Solo puedo responder sobre inflación en México."}'
    )
    monkeypatch.setattr(service, "get_gemini_model", lambda: model)

    result = service.clasificar_consulta_inflacion("¿Quién ganó el partido?")

    assert result["is_valid"] is False
    assert result["respuesta_rechazo"] == "Solo puedo responder sobre inflación en México."
    assert result["fecha_inicio"] is None
    assert result["fecha_fin"] is None
    assert result["monto"] is None


def test_query_without_amount_uses_default_value_from_gemini(monkeypatch, fixed_available_range):
    model = FakeGeminiModel(
        '{"fecha_inicio":"2020-01-01","fecha_fin":"2024-01-01",'
        '"monto":1.0,"is_valid":true,"respuesta_rechazo":""}'
    )
    monkeypatch.setattr(service, "get_gemini_model", lambda: model)

    result = service.clasificar_consulta_inflacion(
        "¿Cuánta inflación hubo entre enero de 2020 y enero de 2024?"
    )

    assert result["monto"] == 1.0
    assert "Si no hay monto explícito, usa 1.0." in model.calls[0][0]


@pytest.mark.parametrize(
    ("start", "end", "expected_message"),
    [
        ("enero-2020", "2024-01-01", "Las fechas no tienen formato YYYY-MM-DD válido."),
        ("1999-12-01", "2024-01-01", "El rango permitido es de 2000-01-01 a 2026-02-01."),
        ("2020-01-01", "2026-03-01", "El rango permitido es de 2000-01-01 a 2026-02-01."),
        ("2024-01-01", "2020-01-01", "La fecha de inicio no puede ser mayor a la fecha final."),
    ],
)
def test_invalid_reversed_or_out_of_range_dates_are_rejected(
    start, end, expected_message, fixed_available_range
):
    result = service.validate_llm_output(
        {
            "fecha_inicio": start,
            "fecha_fin": end,
            "monto": 100,
            "is_valid": True,
            "respuesta_rechazo": "",
        }
    )

    assert result["is_valid"] is False
    assert result["respuesta_rechazo"] == expected_message


def test_missing_inpc_data_returns_controlled_calculation_failure(monkeypatch):
    monkeypatch.setattr(
        service,
        "obtener_inpc_por_fechas",
        lambda *_: {"inpc_inicio": 100.0, "inpc_fin": None},
    )

    result = service.calcular_equivalencia_inflacion(
        {
            "is_valid": True,
            "fecha_inicio": "2020-01-01",
            "fecha_fin": "2024-01-01",
            "monto": 1000,
        }
    )

    assert result["ok"] is False
    assert result["detalle"] is None
    assert "No se encontraron datos" in result["mensaje"]


def test_monetary_equivalence_preserves_current_formula(monkeypatch):
    monkeypatch.setattr(
        service,
        "obtener_inpc_por_fechas",
        lambda *_: {"inpc_inicio": 100.0, "inpc_fin": 125.0},
    )

    result = service.calcular_equivalencia_inflacion(
        {
            "is_valid": True,
            "fecha_inicio": "2020-01-01",
            "fecha_fin": "2024-01-01",
            "monto": 800,
        }
    )

    assert result["ok"] is True
    assert result["detalle"] == {
        "fecha_inicio": "2020-01-01",
        "fecha_fin": "2024-01-01",
        "monto_inicial": 800.0,
        "monto_actualizado": 1000.0,
        "inflacion_pct": 25.0,
        "factor_actualizacion": 1.25,
        "inpc_inicio": 100.0,
        "inpc_fin": 125.0,
    }


def test_historical_inpc_returns_bigquery_dataframe_unchanged(monkeypatch):
    expected = pd.DataFrame(
        {
            "Fecha": pd.to_datetime(["2020-01-01", "2020-02-01"]),
            "INPC": [105.934, 106.889],
        }
    )
    client = FakeBigQueryClient(job=FakeQueryJob(dataframe=expected))
    monkeypatch.setattr(service, "get_bq_client", lambda: client)

    result = service.obtener_historico_inpc("2020-01-01", "2020-02-01")

    pd.testing.assert_frame_equal(result, expected)
    query, job_config = client.calls[0]
    assert "BETWEEN @fecha_inicio AND @fecha_fin" in query
    assert len(job_config.query_parameters) == 2


def test_bigquery_error_becomes_current_controlled_calculation_response(monkeypatch):
    client = FakeBigQueryClient(error=RuntimeError("BigQuery no disponible"))
    monkeypatch.setattr(service, "get_bq_client", lambda: client)

    result = service.calcular_equivalencia_inflacion(
        {
            "is_valid": True,
            "fecha_inicio": "2020-01-01",
            "fecha_fin": "2024-01-01",
            "monto": 100,
        }
    )

    assert result["ok"] is False
    assert result["detalle"] is None
    assert result["mensaje"] == (
        "❌ Error al calcular equivalencia por inflación: BigQuery no disponible"
    )


@pytest.mark.parametrize("response", ["esto no es JSON", "```json\n{JSON inválido}\n```"])
def test_non_json_gemini_response_is_rejected(monkeypatch, fixed_available_range, response):
    monkeypatch.setattr(
        service, "get_gemini_model", lambda: FakeGeminiModel(response=response)
    )

    result = service.clasificar_consulta_inflacion("Consulta de inflación válida")

    assert result == {
        "is_valid": False,
        "respuesta_rechazo": "La respuesta del modelo no fue un JSON válido.",
        "fecha_inicio": None,
        "fecha_fin": None,
        "monto": None,
    }


def test_analytical_comment_is_returned_verbatim(monkeypatch):
    model = FakeGeminiModel("El monto perdió poder adquisitivo durante el periodo.")
    monkeypatch.setattr(service, "get_gemini_model", lambda: model)

    result = service.generar_comentario_analitico(
        {
            "monto_inicial": 100.0,
            "monto_actualizado": 125.0,
            "fecha_inicio": "2020-01-01",
            "fecha_fin": "2024-01-01",
            "inflacion_pct": 25.0,
        }
    )

    assert result == "El monto perdió poder adquisitivo durante el periodo."
    assert "máximo 3 frases" in model.calls[0][0]
    assert "No inventes cifras nuevas" in model.calls[0][0]


def test_gemini_failure_during_classification_returns_rejection(monkeypatch, fixed_available_range):
    monkeypatch.setattr(
        service,
        "get_gemini_model",
        lambda: FakeGeminiModel(error=RuntimeError("Vertex AI no disponible")),
    )

    result = service.clasificar_consulta_inflacion("Consulta de inflación")

    assert result["is_valid"] is False
    assert result["respuesta_rechazo"] == (
        "Error al interpretar la consulta: Vertex AI no disponible"
    )


def test_gemini_failure_during_comment_returns_fallback_text(monkeypatch):
    monkeypatch.setattr(
        service,
        "get_gemini_model",
        lambda: FakeGeminiModel(error=RuntimeError("Vertex AI no disponible")),
    )

    result = service.generar_comentario_analitico(
        {
            "monto_inicial": 100.0,
            "monto_actualizado": 125.0,
            "fecha_inicio": "2020-01-01",
            "fecha_fin": "2024-01-01",
            "inflacion_pct": 25.0,
        }
    )

    assert result == "No se pudo generar el análisis analítico: Vertex AI no disponible"


def test_successful_query_orchestrates_calculation_history_and_comment(monkeypatch):
    intent = {
        "is_valid": True,
        "respuesta_rechazo": "",
        "fecha_inicio": "2020-01-01",
        "fecha_fin": "2024-01-01",
        "monto": 100.0,
    }
    history = pd.DataFrame({"Fecha": [date(2020, 1, 1)], "INPC": [100.0]})
    monkeypatch.setattr(service, "clasificar_consulta_inflacion", lambda *_: intent)
    monkeypatch.setattr(
        service,
        "obtener_inpc_por_fechas",
        lambda *_: {"inpc_inicio": 100.0, "inpc_fin": 125.0},
    )
    monkeypatch.setattr(service, "obtener_historico_inpc", lambda *_: history)
    monkeypatch.setattr(service, "generar_comentario_analitico", lambda *_: "Comentario")

    result = service.procesar_pregunta_inflacion("Consulta válida")

    assert result["pregunta"] == "Consulta válida"
    assert result["intencion"] == intent
    assert result["resultado"]["ok"] is True
    assert result["resultado"]["detalle"]["monto_actualizado"] == 125.0
    assert result["historico"] is history
    assert result["comentario_analitico"] == "Comentario"
    assert "$100.00 MXN" in result["texto_resultado"]
    assert "$125.00 MXN" in result["texto_resultado"]


def test_rejected_query_skips_bigquery_history_and_comment(monkeypatch):
    rejected = {
        "is_valid": False,
        "respuesta_rechazo": "Consulta fuera de dominio.",
        "fecha_inicio": None,
        "fecha_fin": None,
        "monto": None,
    }
    monkeypatch.setattr(service, "clasificar_consulta_inflacion", lambda *_: rejected)

    result = service.procesar_pregunta_inflacion("Consulta rechazada")

    assert result["resultado"] == {
        "ok": False,
        "mensaje": "🚫 Consulta fuera de dominio.",
        "detalle": None,
    }
    assert result["historico"] is None
    assert result["comentario_analitico"] is None
