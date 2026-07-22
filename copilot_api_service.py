from datetime import date, datetime
from typing import Any

import pandas as pd

import inflacion_service
from config import MIN_DATE


INDICATOR = "INPC - General"
SOURCE = "INEGI / BigQuery"


class CopilotApiError(Exception):
    """Base exception for controlled copilot API errors."""


class InvalidCopilotRequestError(CopilotApiError):
    pass


class CopilotQueryRejectedError(CopilotApiError):
    pass


class CopilotDataNotFoundError(CopilotApiError):
    pass


class CopilotDependencyError(CopilotApiError):
    pass


def _parse_date(value: str | None, field_name: str) -> date:
    if not value:
        raise InvalidCopilotRequestError(f"El parametro '{field_name}' es obligatorio.")

    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError) as exc:
        raise InvalidCopilotRequestError(
            f"El parametro '{field_name}' debe tener formato YYYY-MM-DD."
        ) from exc


def _validate_date_range(
    start_date: str | None,
    end_date: str | None,
    max_date: date,
) -> tuple[date, date]:
    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date")

    if start > end:
        raise InvalidCopilotRequestError("start_date no puede ser mayor que end_date.")
    if start < MIN_DATE or end > max_date:
        raise InvalidCopilotRequestError(
            f"El rango permitido es de {MIN_DATE.isoformat()} a {max_date.isoformat()}."
        )

    return start, end


def _serialize_scalar(value: Any) -> Any:
    if value is None or pd.isna(value):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def serialize_history(history: Any) -> list[dict[str, Any]]:
    if history is None:
        return []
    if not isinstance(history, pd.DataFrame):
        raise CopilotDependencyError("No se pudo obtener el historico de INPC.")
    if history.empty:
        return []
    if "Fecha" not in history.columns or "INPC" not in history.columns:
        raise CopilotDependencyError("No se pudo obtener el historico de INPC.")

    ordered = history.sort_values("Fecha")
    return [
        {
            "date": _serialize_scalar(row["Fecha"]),
            "inpc": _serialize_scalar(row["INPC"]),
        }
        for _, row in ordered.iterrows()
    ]


def process_copilot_query(question: str | None) -> dict[str, Any]:
    normalized_question = (question or "").strip()
    if not normalized_question:
        raise InvalidCopilotRequestError("La pregunta es obligatoria.")

    try:
        output = inflacion_service.procesar_pregunta_inflacion(normalized_question)
    except Exception as exc:
        raise CopilotDependencyError(
            "No se pudo procesar la consulta en este momento."
        ) from exc

    intent = output.get("intencion") or {}
    result = output.get("resultado") or {}

    if not intent.get("is_valid"):
        rejection = intent.get("respuesta_rechazo") or "Consulta no valida."
        if rejection.startswith("Error al interpretar la consulta:") or rejection == (
            "La respuesta del modelo no fue un JSON válido."
        ):
            raise CopilotDependencyError(
                "No se pudo interpretar la consulta en este momento."
            )
        raise CopilotQueryRejectedError(rejection)

    if not result.get("ok"):
        message = result.get("mensaje") or "No se pudo calcular la equivalencia."
        if "No se encontraron datos" in message:
            raise CopilotDataNotFoundError(
                "No se encontraron datos INPC para las fechas solicitadas."
            )
        raise CopilotDependencyError(
            "No se pudo calcular la equivalencia en este momento."
        )

    comment = output.get("comentario_analitico")
    if isinstance(comment, str) and comment.startswith(
        "No se pudo generar el análisis analítico:"
    ):
        comment = "No se pudo generar el análisis analítico."

    return {
        "question": normalized_question,
        "intent": intent,
        "result": result,
        "history": serialize_history(output.get("historico")),
        "formatted_result": output.get("texto_resultado"),
        "analytical_comment": comment,
    }


def get_copilot_history(
    start_date: str | None,
    end_date: str | None,
) -> dict[str, Any]:
    try:
        max_date = inflacion_service.obtener_max_fecha_bq()
        start, end = _validate_date_range(start_date, end_date, max_date)
        history = inflacion_service.obtener_historico_inpc(
            start.isoformat(), end.isoformat()
        )
    except InvalidCopilotRequestError:
        raise
    except Exception as exc:
        raise CopilotDependencyError(
            "No se pudo obtener el historico de INPC en este momento."
        ) from exc

    serialized_history = serialize_history(history)
    if not serialized_history:
        raise CopilotDataNotFoundError(
            "No se encontraron datos INPC para el rango solicitado."
        )

    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "indicator": INDICATOR,
        "source": SOURCE,
        "history": serialized_history,
    }


def get_copilot_date_range() -> dict[str, str]:
    try:
        max_date = inflacion_service.obtener_max_fecha_bq()
    except Exception as exc:
        raise CopilotDependencyError(
            "No se pudo obtener el rango de fechas en este momento."
        ) from exc

    return {
        "min_date": MIN_DATE.isoformat(),
        "max_date": max_date.isoformat(),
        "indicator": INDICATOR,
        "source": SOURCE,
    }
