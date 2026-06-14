import os
import re
from datetime import date
from typing import Any

from dotenv import load_dotenv
from google.cloud import bigquery


load_dotenv()

INDICATOR = "INPC - General"
SOURCE = "INEGI / BigQuery"
METHOD = "inflation_pct = ((inpc_end / inpc_start) - 1) * 100"
AVERAGE_PERIOD_METHOD = (
    "inflation_pct = ((avg_inpc_current_period / avg_inpc_previous_period) - 1) * 100"
)
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MIN_YEAR = 2000
MAX_YEAR = 2100


class InflationApiError(Exception):
    """Base exception for controlled API errors."""


class InvalidDateError(InflationApiError):
    pass


class InvalidParameterError(InflationApiError):
    pass


class MissingInflationDataError(InflationApiError):
    pass


class InvalidInpcValueError(InflationApiError):
    pass


class BigQueryConfigError(InflationApiError):
    pass


class BigQueryQueryError(InflationApiError):
    pass


def _parse_required_date(value: str | None, field_name: str) -> date:
    if not value:
        raise InvalidDateError(f"El parametro '{field_name}' es obligatorio.")

    if not DATE_PATTERN.match(value):
        raise InvalidDateError(f"El parametro '{field_name}' debe tener formato YYYY-MM-DD.")

    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise InvalidDateError(f"El parametro '{field_name}' debe ser una fecha valida.") from exc


def _validate_period(start_date: str | None, end_date: str | None) -> tuple[date, date]:
    start = _parse_required_date(start_date, "start_date")
    end = _parse_required_date(end_date, "end_date")

    if start > end:
        raise InvalidDateError("start_date no puede ser mayor que end_date.")

    return start, end


def _parse_required_int(value: int | str | None, field_name: str) -> int:
    if value is None:
        raise InvalidParameterError(f"El parametro '{field_name}' es obligatorio.")

    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise InvalidParameterError(f"El parametro '{field_name}' debe ser entero.") from exc


def _validate_average_period_params(
    current_year: int | str | None,
    previous_year: int | str | None,
    month_limit: int | str | None,
) -> tuple[int, int, int]:
    parsed_current_year = _parse_required_int(current_year, "current_year")
    parsed_previous_year = _parse_required_int(previous_year, "previous_year")
    parsed_month_limit = _parse_required_int(month_limit, "month_limit")

    if not MIN_YEAR <= parsed_current_year <= MAX_YEAR:
        raise InvalidParameterError("current_year debe estar entre 2000 y 2100.")
    if not MIN_YEAR <= parsed_previous_year <= MAX_YEAR:
        raise InvalidParameterError("previous_year debe estar entre 2000 y 2100.")
    if parsed_previous_year > parsed_current_year:
        raise InvalidParameterError("previous_year no puede ser mayor que current_year.")
    if not 1 <= parsed_month_limit <= 12:
        raise InvalidParameterError("month_limit debe estar entre 1 y 12.")

    return parsed_current_year, parsed_previous_year, parsed_month_limit


def _get_bigquery_client() -> bigquery.Client:
    project_id = os.getenv("GCP_PROJECT_ID")
    if not project_id:
        raise BigQueryConfigError("Configuracion incompleta para consultar BigQuery.")

    return bigquery.Client(project=project_id)


def _get_table_id() -> str:
    table_id = os.getenv("GCP_TABLE_ID")
    if not table_id:
        raise BigQueryConfigError("Configuracion incompleta para consultar BigQuery.")
    return table_id


def _row_date_to_iso(row_value: Any) -> str:
    return row_value.isoformat() if hasattr(row_value, "isoformat") else str(row_value)


def get_inpc_values_for_period(
    start: date,
    end: date,
    client: bigquery.Client | None = None,
) -> dict[str, float | None]:
    bq_client = client or _get_bigquery_client()
    table_id = _get_table_id()

    query = f"""
    SELECT
      DATE(Fecha) AS Fecha,
      OBS_VALUE
    FROM `{table_id}`
    WHERE Indicador = 'INPC - General'
      AND DATE(Fecha) IN (@start_date, @end_date)
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("start_date", "DATE", start.isoformat()),
            bigquery.ScalarQueryParameter("end_date", "DATE", end.isoformat()),
        ]
    )

    try:
        rows = list(bq_client.query(query, job_config=job_config).result())
    except Exception as exc:
        raise BigQueryQueryError("Error inesperado al consultar BigQuery.") from exc

    values = {
        "inpc_start": None,
        "inpc_end": None,
    }

    for row in rows:
        row_date = _row_date_to_iso(row["Fecha"])
        obs_value = row["OBS_VALUE"]
        parsed_value = float(obs_value) if obs_value is not None else None

        if row_date == start.isoformat():
            values["inpc_start"] = parsed_value
        if row_date == end.isoformat():
            values["inpc_end"] = parsed_value

    return values


def calculate_inflation_period(
    start_date: str | None,
    end_date: str | None,
    client: bigquery.Client | None = None,
) -> dict[str, Any]:
    start, end = _validate_period(start_date, end_date)
    values = get_inpc_values_for_period(start=start, end=end, client=client)
    inpc_start = values["inpc_start"]
    inpc_end = values["inpc_end"]

    if inpc_start is None:
        raise MissingInflationDataError("No se encontraron datos INPC para start_date.")
    if inpc_end is None:
        raise MissingInflationDataError("No se encontraron datos INPC para end_date.")
    if inpc_start == 0:
        raise InvalidInpcValueError("El INPC inicial es cero; no se puede calcular inflacion.")

    factor = inpc_end / inpc_start
    inflation_pct = (factor - 1) * 100

    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "inpc_start": inpc_start,
        "inpc_end": inpc_end,
        "factor": factor,
        "inflation_pct": inflation_pct,
        "source": SOURCE,
        "indicator": INDICATOR,
        "method": METHOD,
    }


def get_average_inpc_for_period(
    year: int,
    month_limit: int,
    client: bigquery.Client | None = None,
) -> dict[str, Any]:
    bq_client = client or _get_bigquery_client()
    table_id = _get_table_id()

    query = f"""
    SELECT
      AVG(OBS_VALUE) AS avg_inpc,
      MIN(DATE(Fecha)) AS start_date,
      MAX(DATE(Fecha)) AS end_date,
      COUNT(*) AS observations
    FROM `{table_id}`
    WHERE Indicador = 'INPC - General'
      AND EXTRACT(YEAR FROM DATE(Fecha)) = @year
      AND EXTRACT(MONTH FROM DATE(Fecha)) BETWEEN 1 AND @month_limit
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("year", "INT64", year),
            bigquery.ScalarQueryParameter("month_limit", "INT64", month_limit),
        ]
    )

    try:
        rows = list(bq_client.query(query, job_config=job_config).result())
    except Exception as exc:
        raise BigQueryQueryError("Error inesperado al consultar BigQuery.") from exc

    if not rows:
        return {
            "start_date": None,
            "end_date": None,
            "avg_inpc": None,
            "observations": 0,
        }

    row = rows[0]
    avg_inpc = row["avg_inpc"]

    return {
        "start_date": _row_date_to_iso(row["start_date"]) if row["start_date"] else None,
        "end_date": _row_date_to_iso(row["end_date"]) if row["end_date"] else None,
        "avg_inpc": float(avg_inpc) if avg_inpc is not None else None,
        "observations": int(row["observations"] or 0),
    }


def _validate_average_period_data(
    period: dict[str, Any],
    year: int,
    month_limit: int,
    period_name: str,
) -> None:
    if period["avg_inpc"] is None or period["observations"] < month_limit:
        raise MissingInflationDataError(
            f"No hay datos INPC suficientes para el periodo {period_name} ({year})."
        )


def calculate_average_period_inflation(
    current_year: int | str | None,
    previous_year: int | str | None,
    month_limit: int | str | None,
    client: bigquery.Client | None = None,
) -> dict[str, Any]:
    parsed_current_year, parsed_previous_year, parsed_month_limit = (
        _validate_average_period_params(current_year, previous_year, month_limit)
    )

    current_period = get_average_inpc_for_period(
        year=parsed_current_year,
        month_limit=parsed_month_limit,
        client=client,
    )
    previous_period = get_average_inpc_for_period(
        year=parsed_previous_year,
        month_limit=parsed_month_limit,
        client=client,
    )

    _validate_average_period_data(
        current_period,
        parsed_current_year,
        parsed_month_limit,
        "actual",
    )
    _validate_average_period_data(
        previous_period,
        parsed_previous_year,
        parsed_month_limit,
        "previo",
    )

    avg_current = current_period["avg_inpc"]
    avg_previous = previous_period["avg_inpc"]

    if avg_previous == 0:
        raise InvalidInpcValueError(
            "El INPC promedio del periodo previo es cero; no se puede calcular inflacion."
        )

    factor = avg_current / avg_previous
    inflation_pct = (factor - 1) * 100

    return {
        "current_year": parsed_current_year,
        "previous_year": parsed_previous_year,
        "month_limit": parsed_month_limit,
        "comparability": "YTD comparable",
        "current_period": {
            "start_date": current_period["start_date"],
            "end_date": current_period["end_date"],
            "avg_inpc": avg_current,
        },
        "previous_period": {
            "start_date": previous_period["start_date"],
            "end_date": previous_period["end_date"],
            "avg_inpc": avg_previous,
        },
        "factor": factor,
        "inflation_pct": inflation_pct,
        "source": SOURCE,
        "indicator": INDICATOR,
        "method": AVERAGE_PERIOD_METHOD,
    }
