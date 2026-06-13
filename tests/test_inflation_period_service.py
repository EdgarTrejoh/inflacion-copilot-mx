import json

import pytest

from inflation_api_service import (
    InvalidDateError,
    InvalidInpcValueError,
    MissingInflationDataError,
    calculate_inflation_period,
)


def test_calculate_inflation_period_calculates_factor_and_percentage(monkeypatch):
    def fake_get_inpc_values_for_period(start, end, client=None):
        return {
            "inpc_start": 100.0,
            "inpc_end": 112.5,
        }

    monkeypatch.setattr(
        "inflation_api_service.get_inpc_values_for_period",
        fake_get_inpc_values_for_period,
    )

    result = calculate_inflation_period("2024-01-01", "2025-12-01")

    assert result["start_date"] == "2024-01-01"
    assert result["end_date"] == "2025-12-01"
    assert result["inpc_start"] == 100.0
    assert result["inpc_end"] == 112.5
    assert result["factor"] == 1.125
    assert result["inflation_pct"] == 12.5
    assert result["source"] == "INEGI / BigQuery"
    assert result["indicator"] == "INPC - General"
    assert result["method"] == "inflation_pct = ((inpc_end / inpc_start) - 1) * 100"


@pytest.mark.parametrize(
    ("start_date", "end_date"),
    [
        ("2024/01/01", "2025-12-01"),
        ("2024-13-01", "2025-12-01"),
        ("2024-01-01", "2025/12/01"),
    ],
)
def test_calculate_inflation_period_rejects_invalid_dates(start_date, end_date):
    with pytest.raises(InvalidDateError):
        calculate_inflation_period(start_date, end_date)


def test_calculate_inflation_period_rejects_start_after_end():
    with pytest.raises(InvalidDateError):
        calculate_inflation_period("2025-12-01", "2024-01-01")


def test_calculate_inflation_period_missing_start_date():
    with pytest.raises(InvalidDateError):
        calculate_inflation_period(None, "2025-12-01")


def test_calculate_inflation_period_missing_end_date():
    with pytest.raises(InvalidDateError):
        calculate_inflation_period("2024-01-01", None)


def test_calculate_inflation_period_missing_start_inpc(monkeypatch):
    def fake_get_inpc_values_for_period(start, end, client=None):
        return {
            "inpc_start": None,
            "inpc_end": 110.0,
        }

    monkeypatch.setattr(
        "inflation_api_service.get_inpc_values_for_period",
        fake_get_inpc_values_for_period,
    )

    with pytest.raises(MissingInflationDataError, match="start_date"):
        calculate_inflation_period("2024-01-01", "2025-12-01")


def test_calculate_inflation_period_missing_end_inpc(monkeypatch):
    def fake_get_inpc_values_for_period(start, end, client=None):
        return {
            "inpc_start": 100.0,
            "inpc_end": None,
        }

    monkeypatch.setattr(
        "inflation_api_service.get_inpc_values_for_period",
        fake_get_inpc_values_for_period,
    )

    with pytest.raises(MissingInflationDataError, match="end_date"):
        calculate_inflation_period("2024-01-01", "2025-12-01")


def test_calculate_inflation_period_zero_start_inpc(monkeypatch):
    def fake_get_inpc_values_for_period(start, end, client=None):
        return {
            "inpc_start": 0.0,
            "inpc_end": 110.0,
        }

    monkeypatch.setattr(
        "inflation_api_service.get_inpc_values_for_period",
        fake_get_inpc_values_for_period,
    )

    with pytest.raises(InvalidInpcValueError):
        calculate_inflation_period("2024-01-01", "2025-12-01")


def test_calculate_inflation_period_response_is_json_serializable(monkeypatch):
    def fake_get_inpc_values_for_period(start, end, client=None):
        return {
            "inpc_start": 100.0,
            "inpc_end": 105.0,
        }

    monkeypatch.setattr(
        "inflation_api_service.get_inpc_values_for_period",
        fake_get_inpc_values_for_period,
    )

    result = calculate_inflation_period("2024-01-01", "2025-12-01")

    json.dumps(result)


def test_service_errors_do_not_leak_sensitive_details():
    with pytest.raises(InvalidDateError) as exc:
        calculate_inflation_period("2025-12-01", "2024-01-01")

    message = str(exc.value).lower()
    forbidden_terms = [
        "credential",
        "private key",
        "service account",
        "traceback",
        "stack trace",
        "gcp_table_id",
        "datos_economicos_mx.inflacion_historica",
    ]

    for term in forbidden_terms:
        assert term not in message
