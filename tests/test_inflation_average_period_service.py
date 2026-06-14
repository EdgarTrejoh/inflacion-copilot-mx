import json

import pytest

from inflation_api_service import (
    InvalidInpcValueError,
    InvalidParameterError,
    MissingInflationDataError,
    calculate_average_period_inflation,
)


def test_calculate_average_period_inflation_calculates_factor_and_percentage(monkeypatch):
    def fake_get_average_inpc_for_period(year, month_limit, client=None):
        if year == 2025:
            return {
                "start_date": "2025-01-01",
                "end_date": "2025-12-01",
                "avg_inpc": 112.5,
                "observations": 12,
            }
        return {
            "start_date": "2024-01-01",
            "end_date": "2024-12-01",
            "avg_inpc": 100.0,
            "observations": 12,
        }

    monkeypatch.setattr(
        "inflation_api_service.get_average_inpc_for_period",
        fake_get_average_inpc_for_period,
    )

    result = calculate_average_period_inflation(2025, 2024, 12)

    assert result["current_year"] == 2025
    assert result["previous_year"] == 2024
    assert result["month_limit"] == 12
    assert result["comparability"] == "YTD comparable"
    assert result["current_period"]["avg_inpc"] == 112.5
    assert result["previous_period"]["avg_inpc"] == 100.0
    assert result["factor"] == 1.125
    assert result["inflation_pct"] == 12.5
    assert result["source"] == "INEGI / BigQuery"
    assert result["indicator"] == "INPC - General"
    assert result["method"] == (
        "inflation_pct = ((avg_inpc_current_period / avg_inpc_previous_period) - 1) * 100"
    )


@pytest.mark.parametrize("month_limit", [0, 13])
def test_calculate_average_period_inflation_rejects_invalid_month_limit(month_limit):
    with pytest.raises(InvalidParameterError, match="month_limit"):
        calculate_average_period_inflation(2025, 2024, month_limit)


def test_calculate_average_period_inflation_rejects_previous_year_after_current_year():
    with pytest.raises(InvalidParameterError, match="previous_year"):
        calculate_average_period_inflation(2024, 2025, 12)


@pytest.mark.parametrize(
    ("current_year", "previous_year"),
    [
        (1999, 2024),
        (2025, 1999),
        (2101, 2024),
        (2025, 2101),
    ],
)
def test_calculate_average_period_inflation_rejects_year_out_of_range(
    current_year,
    previous_year,
):
    with pytest.raises(InvalidParameterError):
        calculate_average_period_inflation(current_year, previous_year, 12)


@pytest.mark.parametrize(
    ("current_year", "previous_year", "month_limit", "expected_field"),
    [
        (None, 2024, 12, "current_year"),
        (2025, None, 12, "previous_year"),
        (2025, 2024, None, "month_limit"),
    ],
)
def test_calculate_average_period_inflation_rejects_missing_parameters(
    current_year,
    previous_year,
    month_limit,
    expected_field,
):
    with pytest.raises(InvalidParameterError, match=expected_field):
        calculate_average_period_inflation(current_year, previous_year, month_limit)


def test_calculate_average_period_inflation_missing_current_data(monkeypatch):
    def fake_get_average_inpc_for_period(year, month_limit, client=None):
        if year == 2025:
            return {
                "start_date": None,
                "end_date": None,
                "avg_inpc": None,
                "observations": 0,
            }
        return {
            "start_date": "2024-01-01",
            "end_date": "2024-12-01",
            "avg_inpc": 100.0,
            "observations": 12,
        }

    monkeypatch.setattr(
        "inflation_api_service.get_average_inpc_for_period",
        fake_get_average_inpc_for_period,
    )

    with pytest.raises(MissingInflationDataError, match="actual"):
        calculate_average_period_inflation(2025, 2024, 12)


def test_calculate_average_period_inflation_missing_previous_data(monkeypatch):
    def fake_get_average_inpc_for_period(year, month_limit, client=None):
        if year == 2025:
            return {
                "start_date": "2025-01-01",
                "end_date": "2025-12-01",
                "avg_inpc": 112.5,
                "observations": 12,
            }
        return {
            "start_date": None,
            "end_date": None,
            "avg_inpc": None,
            "observations": 0,
        }

    monkeypatch.setattr(
        "inflation_api_service.get_average_inpc_for_period",
        fake_get_average_inpc_for_period,
    )

    with pytest.raises(MissingInflationDataError, match="previo"):
        calculate_average_period_inflation(2025, 2024, 12)


def test_calculate_average_period_inflation_incomplete_observations(monkeypatch):
    def fake_get_average_inpc_for_period(year, month_limit, client=None):
        return {
            "start_date": f"{year}-01-01",
            "end_date": f"{year}-11-01",
            "avg_inpc": 100.0,
            "observations": 11,
        }

    monkeypatch.setattr(
        "inflation_api_service.get_average_inpc_for_period",
        fake_get_average_inpc_for_period,
    )

    with pytest.raises(MissingInflationDataError):
        calculate_average_period_inflation(2025, 2024, 12)


def test_calculate_average_period_inflation_zero_previous_avg(monkeypatch):
    def fake_get_average_inpc_for_period(year, month_limit, client=None):
        if year == 2025:
            return {
                "start_date": "2025-01-01",
                "end_date": "2025-12-01",
                "avg_inpc": 112.5,
                "observations": 12,
            }
        return {
            "start_date": "2024-01-01",
            "end_date": "2024-12-01",
            "avg_inpc": 0.0,
            "observations": 12,
        }

    monkeypatch.setattr(
        "inflation_api_service.get_average_inpc_for_period",
        fake_get_average_inpc_for_period,
    )

    with pytest.raises(InvalidInpcValueError):
        calculate_average_period_inflation(2025, 2024, 12)


def test_calculate_average_period_inflation_response_is_json_serializable(monkeypatch):
    def fake_get_average_inpc_for_period(year, month_limit, client=None):
        return {
            "start_date": f"{year}-01-01",
            "end_date": f"{year}-04-01",
            "avg_inpc": 100.0 if year == 2025 else 95.0,
            "observations": 4,
        }

    monkeypatch.setattr(
        "inflation_api_service.get_average_inpc_for_period",
        fake_get_average_inpc_for_period,
    )

    result = calculate_average_period_inflation(2025, 2024, 4)

    json.dumps(result)


def test_average_period_service_errors_do_not_leak_sensitive_details():
    with pytest.raises(InvalidParameterError) as exc:
        calculate_average_period_inflation(2024, 2025, 12)

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
