export interface CopilotQueryRequest { question: string }

export interface CopilotIntent {
  is_valid: boolean
  respuesta_rechazo: string
  fecha_inicio: string | null
  fecha_fin: string | null
  monto: number | null
}

export interface InflationDetail {
  fecha_inicio: string
  fecha_fin: string
  monto_inicial: number
  monto_actualizado: number
  inflacion_pct: number
  factor_actualizacion: number
  inpc_inicio: number
  inpc_fin: number
}

export interface CopilotCalculation {
  ok: boolean
  mensaje: string
  detalle: InflationDetail | null
}

export interface HistoryPoint { date: string; inpc: number }

export interface CopilotQueryResponse {
  question: string
  intent: CopilotIntent
  result: CopilotCalculation
  history: HistoryPoint[]
  formatted_result: string | null
  analytical_comment: string | null
}

export interface CopilotHistoryResponse {
  start_date: string
  end_date: string
  indicator: string
  source: string
  history: HistoryPoint[]
}

export interface CopilotDateRange {
  min_date: string
  max_date: string
  indicator: string
  source: string
}

export interface BackendErrorResponse { detail: string }
export type ApiErrorKind = "http" | "network" | "invalid-response"
