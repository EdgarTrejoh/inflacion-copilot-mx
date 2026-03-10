import os
import json
from datetime import datetime, date
from typing import Any, Dict, Optional

import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig
from google.cloud import bigquery


# =========================
# CONFIGURACIÓN
# =========================
PROJECT_ID = os.getenv("GCP_PROJECT_ID", "fluted-oath-477301-c1")
LOCATION = os.getenv("GCP_LOCATION", "us-central1")
TABLE_ID = f"{PROJECT_ID}.datos_economicos_mx.inflacion_historica"

MIN_DATE = date(2020, 1, 1)
MAX_DATE = date(2026, 2, 1)  # solo febrero 2026 permitido

vertexai.init(project=PROJECT_ID, location=LOCATION)
bq_client = bigquery.Client(project=PROJECT_ID)


# =========================
# MODELOS
# =========================
def get_gemini_model() -> GenerativeModel:
    return GenerativeModel("gemini-2.5-flash")


# =========================
# UTILIDADES DE VALIDACIÓN
# =========================
def parse_date(value: str) -> date:
    """
    Convierte un string YYYY-MM-DD a objeto date.
    Lanza ValueError si el formato no es válido.
    """
    return datetime.strptime(value, "%Y-%m-%d").date()


def validate_llm_output(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Valida y normaliza la salida del modelo.
    Regresa un dict consistente.
    """
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

    # Si ya viene inválido desde el modelo, respetamos el rechazo
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

    # Regla adicional: si es 2026, solo febrero
    if fecha_inicio.year == 2026 and fecha_inicio != date(2026, 2, 1):
        return {
            "is_valid": False,
            "respuesta_rechazo": "Para 2026 solo se permite febrero (2026-02-01).",
            "fecha_inicio": fecha_inicio.isoformat(),
            "fecha_fin": fecha_fin.isoformat(),
            "monto": monto,
        }

    if fecha_fin.year == 2026 and fecha_fin != date(2026, 2, 1):
        return {
            "is_valid": False,
            "respuesta_rechazo": "Para 2026 solo se permite febrero (2026-02-01).",
            "fecha_inicio": fecha_inicio.isoformat(),
            "fecha_fin": fecha_fin.isoformat(),
            "monto": monto,
        }

    return {
        "is_valid": True,
        "respuesta_rechazo": "",
        "fecha_inicio": fecha_inicio.isoformat(),
        "fecha_fin": fecha_fin.isoformat(),
        "monto": monto,
    }


# =========================
# 1) CLASIFICACIÓN / EXTRACCIÓN
# =========================
def clasificar_consulta_inflacion(pregunta_usuario: str) -> Dict[str, Any]:
    """
    Usa Gemini para interpretar la pregunta y devolver un JSON estructurado.
    Luego valida la salida en Python.
    """
    model = get_gemini_model()

    instrucciones = """
Eres un clasificador experto en inflación mexicana.

Tu tarea es analizar la pregunta del usuario y devolver ÚNICAMENTE un JSON válido
con esta estructura exacta:

{
  "fecha_inicio": "YYYY-MM-DD",
  "fecha_fin": "YYYY-MM-DD",
  "monto": float,
  "is_valid": boolean,
  "respuesta_rechazo": "mensaje si no es válido"
}

Reglas:
- Solo aceptas preguntas sobre inflación en México.
- El rango permitido es de 2020-01-01 a 2026-02-01.
- Si el año es 2026, solo se permite febrero (2026-02-01).
- Si el usuario menciona solo mes y año, usa el día 01.
- Si no hay monto explícito, usa 1.0.
- Si la consulta no corresponde a inflación en México, marca is_valid=false.
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
        validated = validate_llm_output(raw_data)
        return validated

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
# 2) CONSULTA A BIGQUERY
# =========================
def obtener_inpc_por_fechas(fecha_inicio: str, fecha_fin: str) -> Dict[str, Optional[float]]:
    """
    Consulta BigQuery usando parámetros reales.
    Regresa INPC de fecha inicio y fecha fin.
    """
    query = f"""
    SELECT
      Fecha,
      OBS_VALUE
    FROM `{TABLE_ID}`
    WHERE Fecha IN (@fecha_inicio, @fecha_fin)
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("fecha_inicio", "DATE", fecha_inicio),
            bigquery.ScalarQueryParameter("fecha_fin", "DATE", fecha_fin),
        ]
    )

    query_job = bq_client.query(query, job_config=job_config)
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


# =========================
# 3) CÁLCULO
# =========================
def calcular_equivalencia_inflacion(datos: Dict[str, Any]) -> Dict[str, Any]:
    """
    Orquesta la consulta y el cálculo.
    Regresa un diccionario estructurado.
    """
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
# 4) FORMATO DE RESPUESTA
# =========================
def formatear_resultado(resultado: Dict[str, Any], nombre_usuario: str = "Edgar Trejo") -> str:
    """
    Convierte el resultado estructurado en texto amigable.
    """
    if not resultado["ok"]:
        return resultado["mensaje"]

    d = resultado["detalle"]
    return (
        f"✅ **Resultado para {nombre_usuario}:**\n"
        f"💰 ${d['monto_inicial']:,.2f} MXN de {d['fecha_inicio']} equivalen a "
        f"**${d['monto_actualizado']:,.2f} MXN** en {d['fecha_fin']}.\n"
        f"📈 Inflación acumulada: **{d['inflacion_pct']:.2f}%**\n"
        f"📚 Fuente: INEGI / Datos Económicos MX"
    )


# =========================
# 5) COMENTARIO ANALÍTICO
# =========================
def generar_comentario_analitico(detalle: Dict[str, Any]) -> str:
    """
    Genera un comentario narrativo breve usando los datos reales.
    """
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
        return f"No se pudo generar el comentario analítico: {str(e)}"


# =========================
# 6) FLUJO COMPLETO
# =========================
def procesar_pregunta_inflacion(pregunta_usuario: str, nombre_usuario: str = "Edgar Trejo") -> Dict[str, Any]:
    """
    Ejecuta el flujo completo:
    1. Clasifica
    2. Valida
    3. Consulta BigQuery
    4. Calcula
    5. Formatea salida
    6. Genera comentario analítico
    """
    intencion = clasificar_consulta_inflacion(pregunta_usuario)
    resultado = calcular_equivalencia_inflacion(intencion)
    texto_resultado = formatear_resultado(resultado, nombre_usuario=nombre_usuario)

    comentario = None
    if resultado["ok"] and resultado["detalle"]:
        comentario = generar_comentario_analitico(resultado["detalle"])

    return {
        "pregunta": pregunta_usuario,
        "intencion": intencion,
        "resultado": resultado,
        "texto_resultado": texto_resultado,
        "comentario_analitico": comentario,
    }


# =========================
# PRUEBA
# =========================
if __name__ == "__main__":
    pregunta = "¿A cuánto equivalen 100 pesos de enero 2020 a enero 2024?"
    print(f"🤔 Usuario: {pregunta}\n")

    salida = procesar_pregunta_inflacion(pregunta)

    print(salida["texto_resultado"])

    if salida["comentario_analitico"]:
        print("\n🤖 **Análisis del Asistente:**")
        print(salida["comentario_analitico"])