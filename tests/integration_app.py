from datetime import date

import pandas as pd

import inflacion_service
from api.main import app


def _history() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Fecha": pd.to_datetime(["2020-01-01", "2022-01-01", "2024-01-01"]),
            "INPC": [100.0, 112.0, 125.0],
        }
    )


def _query_output(question: str) -> dict:
    if "error interno" in question.lower():
        raise RuntimeError("credencial-interna-no-debe-exponerse")

    if "rechazada" in question.lower():
        return {
            "pregunta": question,
            "intencion": {
                "is_valid": False,
                "respuesta_rechazo": "Solo puedo responder sobre inflación en México.",
                "fecha_inicio": None,
                "fecha_fin": None,
                "monto": None,
            },
            "resultado": {"ok": False, "mensaje": "Consulta no válida.", "detalle": None},
            "historico": None,
            "texto_resultado": "Consulta no válida.",
            "comentario_analitico": None,
        }

    return {
        "pregunta": question,
        "intencion": {
            "is_valid": True,
            "respuesta_rechazo": "",
            "fecha_inicio": "2020-01-01",
            "fecha_fin": "2024-01-01",
            "monto": 800.0,
        },
        "resultado": {
            "ok": True,
            "mensaje": "Cálculo realizado correctamente.",
            "detalle": {
                "fecha_inicio": "2020-01-01",
                "fecha_fin": "2024-01-01",
                "monto_inicial": 800.0,
                "monto_actualizado": 1000.0,
                "inflacion_pct": 25.0,
                "factor_actualizacion": 1.25,
                "inpc_inicio": 100.0,
                "inpc_fin": 125.0,
            },
        },
        "historico": _history(),
        "texto_resultado": "Resultado local de integración.",
        "comentario_analitico": (
            None
            if "sin comentario" in question.lower()
            else "El poder adquisitivo disminuyó durante el periodo."
        ),
    }


inflacion_service.procesar_pregunta_inflacion = _query_output
inflacion_service.obtener_historico_inpc = lambda *_args: _history()
inflacion_service.obtener_max_fecha_bq = lambda: date(2026, 2, 1)
