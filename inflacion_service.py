import os
import json
from datetime import datetime, date
from typing import Any, Dict, Optional
from dotenv import load_dotenv

load_dotenv()

import streamlit as st
import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig
from google.cloud import bigquery


# =========================
# CONFIGURACIÓN
# =========================
PROJECT_ID = os.getenv("GCP_PROJECT_ID")
LOCATION = os.getenv("GCP_LOCATION")
TABLE_ID = os.getenv("GCP_TABLE_ID")

from config import MIN_DATE, MAX_DATE


# =========================
# RECURSOS CACHEADOS
# =========================
@st.cache_resource
def get_bq_client() -> bigquery.Client:
    return bigquery.Client(project=PROJECT_ID)


@st.cache_resource
def init_vertex() -> bool:
    vertexai.init(project=PROJECT_ID, location=LOCATION)
    return True


def get_gemini_model() -> GenerativeModel:
    init_vertex()
    return GenerativeModel("gemini-2.5-flash")


# =========================
# VALIDACIÓN
# =========================
def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def validate_llm_output(data: Dict[str, Any]) -> Dict[str, Any]:
    required_keys = {
        "fecha_inicio",
        "fecha_fin",
        "monto",
        "is_valid",
        "respuesta_rechazo",
    }

    missing = required_keys - set(data.keys())
    if missing:
        return {
            "is_valid": False,
            "respuesta_rechazo": f"Faltan campos en la respuesta del modelo: {sorted(missing)}",
            "fecha_inicio": None,
            "fecha_fin": None,
            "monto": None,
        }

    if not isinstance(data["is_valid"], bool):
        return {
            "is_valid": False,
            "respuesta_rechazo": "El campo 'is_valid' no es booleano.",
            "fecha_inicio": None,
            "fecha_fin": None,
            "monto": None,
        }

    if not data["is_valid"]:
        return {
            "is_valid": False,
            "respuesta_rechazo": data.get("respuesta_rechazo") or "Consulta no válida.",
            "fecha_inicio": data.get("fecha_inicio"),
            "fecha_fin": data.get("fecha_fin"),
            "monto": data.get("monto"),
        }

    try:
        fecha_inicio = parse_date(data["fecha_inicio"])
        fecha_fin = parse_date(data["fecha_fin"])
    except Exception:
        return {
            "is_valid": False,
            "respuesta_rechazo": "Las fechas no tienen formato YYYY-MM-DD válido.",
            "fecha_inicio": None,
            "fecha_fin": None,
            "monto": None,
        }

    try:
        monto = float(data["monto"])
    except Exception:
        return {
            "is_valid": False,
            "respuesta_rechazo": "El monto no es numérico.",
            "fecha_inicio": None,
            "fecha_fin": None,
            "monto": None,
        }

    if monto <= 0:
        return {
            "is_valid": False,
            "respuesta_rechazo": "El monto debe ser mayor a cero.",
            "fecha_inicio": fecha_inicio.isoformat(),
            "fecha_fin": fecha_fin.isoformat(),
            "monto": monto,
        }

    if fecha_inicio > fecha_fin:
        return {
            "is_valid": False,
            "respuesta_rechazo": "La fecha de inicio no puede ser mayor a la fecha final.",
            "fecha_inicio": fecha_inicio.isoformat(),
            "fecha_fin": fecha_fin.isoformat(),
            "monto": monto,
        }

    if fecha_inicio < MIN_DATE or fecha_fin > MAX_DATE:
        return {
            "is_valid": False,
            "respuesta_rechazo": (
                f"El rango permitido es de {MIN_DATE.isoformat()} a {MAX_DATE.isoformat()}."
            ),
            "fecha_inicio": fecha_inicio.isoformat(),
            "fecha_fin": fecha_fin.isoformat(),
            "monto": monto,
        }

    # La validación fecha_fin > MAX_DATE ya captura que no sean mayores a MAX_DATE.
    # Por lo que no es necesario restringir otros meses válidos en 2026 antes o iguales a la fecha máxima.

    return {
        "is_valid": True,
        "respuesta_rechazo": "",
        "fecha_inicio": fecha_inicio.isoformat(),
        "fecha_fin": fecha_fin.isoformat(),
        "monto": monto,
    }


# =========================
# IA: CLASIFICACIÓN
# =========================
def clasificar_consulta_inflacion(pregunta_usuario: str) -> Dict[str, Any]:
    model = get_gemini_model()

    instrucciones = """
Eres un extractor de datos para una calculadora de inflación mexicana.

Devuelve ÚNICAMENTE un JSON válido con esta estructura exacta:
{
  "fecha_inicio": "YYYY-MM-DD",
  "fecha_fin": "YYYY-MM-DD",
  "monto": float,
  "is_valid": boolean,
  "respuesta_rechazo": "string"
}

Reglas:
- Solo aceptas preguntas sobre inflación o poder adquisitivo en México.
- El rango permitido es de {MIN_DATE.isoformat()} a {MAX_DATE.isoformat()}.
- Si el usuario menciona solo mes y año, usa el día 01.
- Si no hay monto explícito, usa 1.0.
- Si no es una consulta válida sobre inflación en México, marca is_valid=false.
- Devuelve siempre todas las llaves.
- No agregues texto fuera del JSON.
"""

    config = GenerationConfig(
        temperature=0.0,
        response_mime_type="application/json",
    )

    try:
        response = model.generate_content(
            f"{instrucciones}\n\nPregunta del usuario: {pregunta_usuario}",
            generation_config=config,
        )
        raw_data = json.loads(response.text)
        return validate_llm_output(raw_data)

    except json.JSONDecodeError:
        return {
            "is_valid": False,
            "respuesta_rechazo": "La respuesta del modelo no fue un JSON válido.",
            "fecha_inicio": None,
            "fecha_fin": None,
            "monto": None,
        }
    except Exception as e:
        return {
            "is_valid": False,
            "respuesta_rechazo": f"Error al interpretar la consulta: {str(e)}",
            "fecha_inicio": None,
            "fecha_fin": None,
            "monto": None,
        }


# =========================
# BIGQUERY
# =========================
def obtener_inpc_por_fechas(fecha_inicio: str, fecha_fin: str) -> Dict[str, Optional[float]]:
    client = get_bq_client()

    query = f"""
    SELECT
      DATE(Fecha) AS Fecha,
      OBS_VALUE
    FROM `{TABLE_ID}`
    WHERE Indicador = 'INPC - General'
      AND DATE(Fecha) IN (@fecha_inicio, @fecha_fin)
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("fecha_inicio", "DATE", fecha_inicio),
            bigquery.ScalarQueryParameter("fecha_fin", "DATE", fecha_fin),
        ]
    )

    query_job = client.query(query, job_config=job_config)
    rows = list(query_job.result())

    resultados = {
        "inpc_inicio": None,
        "inpc_fin": None,
    }

    for row in rows:
        fecha_row = row["Fecha"].isoformat() if hasattr(row["Fecha"], "isoformat") else str(row["Fecha"])
        if fecha_row == fecha_inicio:
            resultados["inpc_inicio"] = float(row["OBS_VALUE"])
        elif fecha_row == fecha_fin:
            resultados["inpc_fin"] = float(row["OBS_VALUE"])

    return resultados


@st.cache_data(show_spinner=False)
def obtener_historico_inpc(fecha_inicio: str, fecha_fin: str):
    client = get_bq_client()

    query = f"""
    SELECT
      DATE(Fecha) AS Fecha,
      OBS_VALUE AS INPC
    FROM `{TABLE_ID}`
    WHERE Indicador = 'INPC - General'
        AND DATE(Fecha) BETWEEN @fecha_inicio AND @fecha_fin
    ORDER BY Fecha
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("fecha_inicio", "DATE", fecha_inicio),
            bigquery.ScalarQueryParameter("fecha_fin", "DATE", fecha_fin),
        ]
    )

    return client.query(query, job_config=job_config).to_dataframe()


# =========================
# CÁLCULO
# =========================
def calcular_equivalencia_inflacion(datos: Dict[str, Any]) -> Dict[str, Any]:
    if not datos.get("is_valid"):
        return {
            "ok": False,
            "mensaje": f"🚫 {datos.get('respuesta_rechazo', 'Consulta no válida.')}",
            "detalle": None,
        }

    try:
        fecha_inicio = datos["fecha_inicio"]
        fecha_fin = datos["fecha_fin"]
        monto = float(datos["monto"])

        inpc = obtener_inpc_por_fechas(fecha_inicio, fecha_fin)
        inpc_inicio = inpc["inpc_inicio"]
        inpc_fin = inpc["inpc_fin"]

        if inpc_inicio is None or inpc_fin is None:
            return {
                "ok": False,
                "mensaje": (
                    f"⚠️ No se encontraron datos para las fechas "
                    f"{fecha_inicio} o {fecha_fin}."
                ),
                "detalle": None,
            }

        if inpc_inicio == 0:
            return {
                "ok": False,
                "mensaje": "⚠️ El INPC inicial es cero; no se puede calcular el factor de actualización.",
                "detalle": None,
            }

        factor = inpc_fin / inpc_inicio
        monto_actualizado = monto * factor
        inflacion_pct = (factor - 1) * 100

        detalle = {
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin,
            "monto_inicial": monto,
            "monto_actualizado": monto_actualizado,
            "inflacion_pct": inflacion_pct,
            "factor_actualizacion": factor,
            "inpc_inicio": inpc_inicio,
            "inpc_fin": inpc_fin,
        }

        return {
            "ok": True,
            "mensaje": "Cálculo realizado correctamente.",
            "detalle": detalle,
        }

    except Exception as e:
        return {
            "ok": False,
            "mensaje": f"❌ Error al calcular equivalencia por inflación: {str(e)}",
            "detalle": None,
        }


# =========================
# IA: ANÁLISIS NARRATIVO
# =========================
def generar_comentario_analitico(detalle: Dict[str, Any]) -> str:
    model = get_gemini_model()

    prompt = f"""
Eres un analista económico experto.

Contexto:
Un usuario calculó que ${detalle['monto_inicial']:,.2f} MXN en {detalle['fecha_inicio']}
equivalen a ${detalle['monto_actualizado']:,.2f} MXN en {detalle['fecha_fin']},
debido a una inflación acumulada de {detalle['inflacion_pct']:.2f}%.

Tarea:
Escribe un comentario breve en español, máximo 3 frases.
Explica la pérdida de poder adquisitivo de forma clara, directa y profesional.
No inventes cifras nuevas.
"""

    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"No se pudo generar el análisis analítico: {str(e)}"


# =========================
# ORQUESTADOR
# =========================
def procesar_pregunta_inflacion(pregunta_usuario: str) -> Dict[str, Any]:
    intencion = clasificar_consulta_inflacion(pregunta_usuario)
    resultado = calcular_equivalencia_inflacion(intencion)

    historico = None
    comentario = None

    if resultado["ok"] and resultado["detalle"]:
        detalle = resultado["detalle"]
        historico = obtener_historico_inpc(
            detalle["fecha_inicio"],
            detalle["fecha_fin"]
        )
        comentario = generar_comentario_analitico(detalle)

    return {
        "pregunta": pregunta_usuario,
        "intencion": intencion,
        "resultado": resultado,
        "historico": historico,
        "comentario_analitico": comentario,
    }