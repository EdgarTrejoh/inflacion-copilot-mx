import json

import pytest

from inflation_api_service import (
    InvalidInpcValueError,
    InvalidParameterError,
    MissingInflationDataError,
    calculate_monthly_comparable_inflation,
)


def test_calculate_monthly_comparable_inflation_calculates_factors(monkeypatch):
    def fake_get_monthly_inpc_for_years(current_year, previous_year, month_limit, client=None):
        assert current_year == 2026
        assert previous_year == 2025
        assert month_limit == 2
        return {
            (2026, 1): 140.1,
            (2025, 1): 134.2,
            (2026, 2): 141.0,
            (2025, 2): 135.0,
        }

    monkeypatch.setattr(
        "inflation_api_service.get_monthly_inpc_for_years",
        fake_get_monthly_inpc_for_years,
    )

    result = calculate_monthly_comparable_inflation(2026, 2025, 2)

    assert result["current_year"] == 2026
    assert result["previous_year"] == 2025
    assert result["month_limit"] == 2
    assert result["comparability"] == "monthly_same_month"
    assert result["warnings"] == []
    assert result["factors"][0] == {
        "month": 1,
        "current_period": "2026-01",
        "previous_period": "2025-01",
        "current_inpc": 140.1,
        "previous_inpc": 134.2,
        "factor": 140.1 / 134.2,
        "inflation_pct": ((140.1 / 134.2) - 1) * 100,
    }
    assert result["factors"][1]["current_period"] == "2026-02"
    assert result["source"] == "INEGI / BigQuery"
    assert result["indicator"] == "INPC - General"
    assert result["method"] == "factor = current_month_inpc / previous_same_month_inpc"


def test_calculate_monthly_comparable_inflation_warns_and_omits_missing_month(monkeypatch):
    def fake_get_monthly_inpc_for_years(current_year, previous_year, month_limit, client=None):
        return {
            (2026, 1): 140.1,
            (2025, 1): 134.2,
            (2026, 2): 141.0,
        }

    monkeypatch.setattr(
        "inflation_api_service.get_monthly_inpc_for_years",
        fake_get_monthly_inpc_for_years,
    )

    result = calculate_monthly_comparable_inflation(2026, 2025, 2)

    assert len(result["factors"]) == 1
    assert result["factors"][0]["month"] == 1
    assert result["warnings"] == [
        "No se encontraron datos INPC para 2025-02; mes 2 omitido."
    ]


@pytest.mark.parametrize("month_limit", [0, 13])
def test_calculate_monthly_comparable_inflation_rejects_invalid_month_limit(month_limit):
    with pytest.raises(InvalidParameterError, match="month_limit"):
        calculate_monthly_comparable_inflation(2026, 2025, month_limit)


def test_calculate_monthly_comparable_inflation_rejects_previous_year_after_current_year():
    with pytest.raises(InvalidParameterError, match="previous_year"):
        calculate_monthly_comparable_inflation(2025, 2026, 4)


@pytest.mark.parametrize(
    ("current_year", "previous_year", "month_limit", "expected_field"),
    [
        (None, 2025, 4, "current_year"),
        (2026, None, 4, "previous_year"),
        (2026, 2025, None, "month_limit"),
    ],
)
def test_calculate_monthly_comparable_inflation_rejects_missing_parameters(
    current_year,
    previous_year,
    month_limit,
    expected_field,
):
    with pytest.raises(InvalidParameterError, match=expected_field):
        calculate_monthly_comparable_inflation(current_year, previous_year, month_limit)


def test_calculate_monthly_comparable_inflation_missing_all_pairs(monkeypatch):
    def fake_get_monthly_inpc_for_years(current_year, previous_year, month_limit, client=None):
        return {(2026, 1): 140.1}

    monkeypatch.setattr(
        "inflation_api_service.get_monthly_inpc_for_years",
        fake_get_monthly_inpc_for_years,
    )

    with pytest.raises(MissingInflationDataError, match="pares mensuales"):
        calculate_monthly_comparable_inflation(2026, 2025, 1)


def test_calculate_monthly_comparable_inflation_zero_previous_inpc(monkeypatch):
    def fake_get_monthly_inpc_for_years(current_year, previous_year, month_limit, client=None):
        return {
            (2026, 1): 140.1,
            (2025, 1): 0.0,
        }

    monkeypatch.setattr(
        "inflation_api_service.get_monthly_inpc_for_years",
        fake_get_monthly_inpc_for_years,
    )

    with pytest.raises(InvalidInpcValueError, match="2025-01"):
        calculate_monthly_comparable_inflation(2026, 2025, 1)


def test_calculate_monthly_comparable_inflation_response_is_json_serializable(monkeypatch):
    def fake_get_monthly_inpc_for_years(current_year, previous_year, month_limit, client=None):
        return {
            (2026, 1): 140.1,
            (2025, 1): 134.2,
        }

    monkeypatch.setattr(
        "inflation_api_service.get_monthly_inpc_for_years",
        fake_get_monthly_inpc_for_years,
    )

    result = calculate_monthly_comparable_inflation(2026, 2025, 1)

    json.dumps(result)


def test_monthly_comparable_service_errors_do_not_leak_sensitive_details():
    with pytest.raises(InvalidParameterError) as exc:
        calculate_monthly_comparable_inflation(2025, 2026, 4)

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
