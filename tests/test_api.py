from fastapi.testclient import TestClient

from api.main import app
from inflation_api_service import (
    InvalidInpcValueError,
    InvalidParameterError,
    MissingInflationDataError,
)


client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "inflacion-copilot-api",
    }


def test_inflation_period_returns_200_with_mocked_data(monkeypatch):
    expected = {
        "start_date": "2024-01-01",
        "end_date": "2025-12-01",
        "inpc_start": 100.0,
        "inpc_end": 110.0,
        "factor": 1.1,
        "inflation_pct": 10.0,
        "source": "INEGI / BigQuery",
        "indicator": "INPC - General",
        "method": "inflation_pct = ((inpc_end / inpc_start) - 1) * 100",
    }

    def fake_calculate_inflation_period(start_date, end_date):
        assert start_date == "2024-01-01"
        assert end_date == "2025-12-01"
        return expected

    monkeypatch.setattr("api.main.calculate_inflation_period", fake_calculate_inflation_period)

    response = client.get(
        "/inflation/period?start_date=2024-01-01&end_date=2025-12-01"
    )

    assert response.status_code == 200
    assert response.json() == expected


def test_inflation_period_invalid_date_returns_400():
    response = client.get(
        "/inflation/period?start_date=2024/01/01&end_date=2025-12-01"
    )

    assert response.status_code == 400
    assert "YYYY-MM-DD" in response.json()["detail"]


def test_inflation_period_start_after_end_returns_400():
    response = client.get(
        "/inflation/period?start_date=2025-12-01&end_date=2024-01-01"
    )

    assert response.status_code == 400
    assert "start_date no puede ser mayor" in response.json()["detail"]


def test_inflation_period_missing_start_date_returns_controlled_error():
    response = client.get("/inflation/period?end_date=2025-12-01")

    assert response.status_code == 400
    assert "start_date" in response.json()["detail"]


def test_inflation_period_missing_end_date_returns_controlled_error():
    response = client.get("/inflation/period?start_date=2024-01-01")

    assert response.status_code == 400
    assert "end_date" in response.json()["detail"]


def test_inflation_period_missing_start_inpc_returns_404(monkeypatch):
    def fake_calculate_inflation_period(start_date, end_date):
        raise MissingInflationDataError("No se encontraron datos INPC para start_date.")

    monkeypatch.setattr("api.main.calculate_inflation_period", fake_calculate_inflation_period)

    response = client.get(
        "/inflation/period?start_date=2024-01-01&end_date=2025-12-01"
    )

    assert response.status_code == 404
    assert "start_date" in response.json()["detail"]


def test_inflation_period_missing_end_inpc_returns_404(monkeypatch):
    def fake_calculate_inflation_period(start_date, end_date):
        raise MissingInflationDataError("No se encontraron datos INPC para end_date.")

    monkeypatch.setattr("api.main.calculate_inflation_period", fake_calculate_inflation_period)

    response = client.get(
        "/inflation/period?start_date=2024-01-01&end_date=2025-12-01"
    )

    assert response.status_code == 404
    assert "end_date" in response.json()["detail"]


def test_inflation_period_zero_start_inpc_returns_400(monkeypatch):
    def fake_calculate_inflation_period(start_date, end_date):
        raise InvalidInpcValueError("El INPC inicial es cero; no se puede calcular inflacion.")

    monkeypatch.setattr("api.main.calculate_inflation_period", fake_calculate_inflation_period)

    response = client.get(
        "/inflation/period?start_date=2024-01-01&end_date=2025-12-01"
    )

    assert response.status_code == 400
    assert "INPC inicial es cero" in response.json()["detail"]


def test_api_errors_do_not_leak_sensitive_details():
    response = client.get(
        "/inflation/period?start_date=2025-12-01&end_date=2024-01-01"
    )
    body = response.text.lower()

    forbidden_terms = [
        "credential",
        "private key",
        "service account",
        "traceback",
        "stack trace",
        "gcp_table_id",
        "datos_economicos_mx.inflacion_historica",
    ]

    assert response.status_code == 400
    for term in forbidden_terms:
        assert term not in body


def test_inflation_average_period_returns_200_with_mocked_data(monkeypatch):
    expected = {
        "current_year": 2025,
        "previous_year": 2024,
        "month_limit": 12,
        "comparability": "YTD comparable",
        "current_period": {
            "start_date": "2025-01-01",
            "end_date": "2025-12-01",
            "avg_inpc": 110.0,
        },
        "previous_period": {
            "start_date": "2024-01-01",
            "end_date": "2024-12-01",
            "avg_inpc": 100.0,
        },
        "factor": 1.1,
        "inflation_pct": 10.0,
        "source": "INEGI / BigQuery",
        "indicator": "INPC - General",
        "method": "inflation_pct = ((avg_inpc_current_period / avg_inpc_previous_period) - 1) * 100",
    }

    def fake_calculate_average_period_inflation(current_year, previous_year, month_limit):
        assert current_year == 2025
        assert previous_year == 2024
        assert month_limit == 12
        return expected

    monkeypatch.setattr(
        "api.main.calculate_average_period_inflation",
        fake_calculate_average_period_inflation,
    )

    response = client.get(
        "/inflation/average-period?current_year=2025&previous_year=2024&month_limit=12"
    )

    assert response.status_code == 200
    assert response.json() == expected


def test_inflation_average_period_rejects_month_limit_zero():
    response = client.get(
        "/inflation/average-period?current_year=2025&previous_year=2024&month_limit=0"
    )

    assert response.status_code == 400
    assert "month_limit" in response.json()["detail"]


def test_inflation_average_period_rejects_month_limit_thirteen():
    response = client.get(
        "/inflation/average-period?current_year=2025&previous_year=2024&month_limit=13"
    )

    assert response.status_code == 400
    assert "month_limit" in response.json()["detail"]


def test_inflation_average_period_rejects_previous_year_after_current_year():
    response = client.get(
        "/inflation/average-period?current_year=2024&previous_year=2025&month_limit=12"
    )

    assert response.status_code == 400
    assert "previous_year" in response.json()["detail"]


def test_inflation_average_period_rejects_year_out_of_range():
    response = client.get(
        "/inflation/average-period?current_year=1999&previous_year=2024&month_limit=12"
    )

    assert response.status_code == 400
    assert "current_year" in response.json()["detail"]


def test_inflation_average_period_missing_current_year_returns_controlled_error():
    response = client.get(
        "/inflation/average-period?previous_year=2024&month_limit=12"
    )

    assert response.status_code == 400
    assert "current_year" in response.json()["detail"]


def test_inflation_average_period_missing_previous_year_returns_controlled_error():
    response = client.get(
        "/inflation/average-period?current_year=2025&month_limit=12"
    )

    assert response.status_code == 400
    assert "previous_year" in response.json()["detail"]


def test_inflation_average_period_missing_month_limit_returns_controlled_error():
    response = client.get(
        "/inflation/average-period?current_year=2025&previous_year=2024"
    )

    assert response.status_code == 400
    assert "month_limit" in response.json()["detail"]


def test_inflation_average_period_missing_current_data_returns_404(monkeypatch):
    def fake_calculate_average_period_inflation(current_year, previous_year, month_limit):
        raise MissingInflationDataError("No hay datos INPC suficientes para el periodo actual (2025).")

    monkeypatch.setattr(
        "api.main.calculate_average_period_inflation",
        fake_calculate_average_period_inflation,
    )

    response = client.get(
        "/inflation/average-period?current_year=2025&previous_year=2024&month_limit=12"
    )

    assert response.status_code == 404
    assert "actual" in response.json()["detail"]


def test_inflation_average_period_missing_previous_data_returns_404(monkeypatch):
    def fake_calculate_average_period_inflation(current_year, previous_year, month_limit):
        raise MissingInflationDataError("No hay datos INPC suficientes para el periodo previo (2024).")

    monkeypatch.setattr(
        "api.main.calculate_average_period_inflation",
        fake_calculate_average_period_inflation,
    )

    response = client.get(
        "/inflation/average-period?current_year=2025&previous_year=2024&month_limit=12"
    )

    assert response.status_code == 404
    assert "previo" in response.json()["detail"]


def test_inflation_average_period_zero_previous_avg_returns_400(monkeypatch):
    def fake_calculate_average_period_inflation(current_year, previous_year, month_limit):
        raise InvalidInpcValueError(
            "El INPC promedio del periodo previo es cero; no se puede calcular inflacion."
        )

    monkeypatch.setattr(
        "api.main.calculate_average_period_inflation",
        fake_calculate_average_period_inflation,
    )

    response = client.get(
        "/inflation/average-period?current_year=2025&previous_year=2024&month_limit=12"
    )

    assert response.status_code == 400
    assert "periodo previo es cero" in response.json()["detail"]


def test_inflation_average_period_errors_do_not_leak_sensitive_details():
    response = client.get(
        "/inflation/average-period?current_year=2024&previous_year=2025&month_limit=12"
    )
    body = response.text.lower()

    forbidden_terms = [
        "credential",
        "private key",
        "service account",
        "traceback",
        "stack trace",
        "gcp_table_id",
        "datos_economicos_mx.inflacion_historica",
    ]

    assert response.status_code == 400
    for term in forbidden_terms:
        assert term not in body


def test_inflation_monthly_comparable_returns_200_with_mocked_data(monkeypatch):
    expected = {
        "current_year": 2026,
        "previous_year": 2025,
        "month_limit": 1,
        "comparability": "monthly_same_month",
        "factors": [
            {
                "month": 1,
                "current_period": "2026-01",
                "previous_period": "2025-01",
                "current_inpc": 140.1,
                "previous_inpc": 134.2,
                "factor": 1.0439642324888228,
                "inflation_pct": 4.3964232488822755,
            }
        ],
        "warnings": [],
        "source": "INEGI / BigQuery",
        "indicator": "INPC - General",
        "method": "factor = current_month_inpc / previous_same_month_inpc",
    }

    def fake_calculate_monthly_comparable_inflation(
        current_year,
        previous_year,
        month_limit,
    ):
        assert current_year == 2026
        assert previous_year == 2025
        assert month_limit == 1
        return expected

    monkeypatch.setattr(
        "api.main.calculate_monthly_comparable_inflation",
        fake_calculate_monthly_comparable_inflation,
    )

    response = client.get(
        "/inflation/monthly-comparable?current_year=2026&previous_year=2025&month_limit=1"
    )

    assert response.status_code == 200
    assert response.json() == expected


def test_inflation_monthly_comparable_rejects_month_limit_zero():
    response = client.get(
        "/inflation/monthly-comparable?current_year=2026&previous_year=2025&month_limit=0"
    )

    assert response.status_code == 400
    assert "month_limit" in response.json()["detail"]


def test_inflation_monthly_comparable_rejects_month_limit_thirteen():
    response = client.get(
        "/inflation/monthly-comparable?current_year=2026&previous_year=2025&month_limit=13"
    )

    assert response.status_code == 400
    assert "month_limit" in response.json()["detail"]


def test_inflation_monthly_comparable_missing_month_limit_returns_controlled_error():
    response = client.get(
        "/inflation/monthly-comparable?current_year=2026&previous_year=2025"
    )

    assert response.status_code == 400
    assert "month_limit" in response.json()["detail"]


def test_inflation_monthly_comparable_missing_data_returns_404(monkeypatch):
    def fake_calculate_monthly_comparable_inflation(
        current_year,
        previous_year,
        month_limit,
    ):
        raise MissingInflationDataError(
            "No hay pares mensuales INPC comparables para los parametros solicitados."
        )

    monkeypatch.setattr(
        "api.main.calculate_monthly_comparable_inflation",
        fake_calculate_monthly_comparable_inflation,
    )

    response = client.get(
        "/inflation/monthly-comparable?current_year=2026&previous_year=2025&month_limit=1"
    )

    assert response.status_code == 404
    assert "pares mensuales" in response.json()["detail"]


def test_inflation_monthly_comparable_zero_previous_inpc_returns_400(monkeypatch):
    def fake_calculate_monthly_comparable_inflation(
        current_year,
        previous_year,
        month_limit,
    ):
        raise InvalidInpcValueError(
            "El INPC previo de 2025-01 es cero; no se puede calcular inflacion."
        )

    monkeypatch.setattr(
        "api.main.calculate_monthly_comparable_inflation",
        fake_calculate_monthly_comparable_inflation,
    )

    response = client.get(
        "/inflation/monthly-comparable?current_year=2026&previous_year=2025&month_limit=1"
    )

    assert response.status_code == 400
    assert "2025-01" in response.json()["detail"]


def test_inflation_monthly_comparable_errors_do_not_leak_sensitive_details():
    response = client.get(
        "/inflation/monthly-comparable?current_year=2025&previous_year=2026&month_limit=4"
    )
    body = response.text.lower()

    forbidden_terms = [
        "credential",
        "private key",
        "service account",
        "traceback",
        "stack trace",
        "gcp_table_id",
        "datos_economicos_mx.inflacion_historica",
    ]

    assert response.status_code == 400
    for term in forbidden_terms:
        assert term not in body
