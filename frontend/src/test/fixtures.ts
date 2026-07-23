import type { CopilotDateRange, CopilotQueryResponse } from "../types/api"

export const dateRange: CopilotDateRange = {
  min_date: "2000-01-01", max_date: "2026-02-01", indicator: "INPC - General", source: "INEGI / BigQuery",
}

export function successfulResponse(): CopilotQueryResponse {
  return {
    question: "¿A cuánto equivalen 800 pesos de 2020 a 2024?",
    intent: { is_valid: true, respuesta_rechazo: "", fecha_inicio: "2020-01-01", fecha_fin: "2024-01-01", monto: 800 },
    result: { ok: true, mensaje: "Cálculo realizado correctamente.", detalle: {
      fecha_inicio: "2020-01-01", fecha_fin: "2024-01-01", monto_inicial: 800,
      monto_actualizado: 1000, inflacion_pct: 25, factor_actualizacion: 1.25, inpc_inicio: 100, inpc_fin: 125,
    } },
    history: [{ date: "2024-01-01", inpc: 125 }, { date: "2020-01-01", inpc: 100 }],
    formatted_result: "Resultado", analytical_comment: "El dinero perdió poder adquisitivo durante el periodo.",
  }
}
