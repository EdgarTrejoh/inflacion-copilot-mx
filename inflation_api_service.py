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
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class InflationApiError(Exception):
    """Base exception for controlled API errors."""


class InvalidDateError(InflationApiError):
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
