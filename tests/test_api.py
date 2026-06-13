from fastapi.testclient import TestClient

from api.main import app
from inflation_api_service import InvalidInpcValueError, MissingInflationDataError


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
