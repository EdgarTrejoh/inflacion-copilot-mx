import type { ApiErrorKind, BackendErrorResponse, CopilotDateRange, CopilotHistoryResponse, CopilotQueryRequest, CopilotQueryResponse } from "../types/api"

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL?.trim() ?? "").replace(/\/$/, "")

export class ApiClientError extends Error {
  constructor(message: string, public readonly kind: ApiErrorKind, public readonly status?: number) {
    super(message)
    this.name = "ApiClientError"
  }
}

async function request<T>(baseUrl: string, path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${baseUrl}${path}`, {
      ...init,
      headers: { Accept: "application/json", ...(init?.body ? { "Content-Type": "application/json" } : {}), ...init?.headers },
    })
  } catch {
    throw new ApiClientError("No pudimos comunicarnos con el servicio. Revisa tu conexión e intenta nuevamente.", "network")
  }

  let payload: unknown
  try {
    payload = await response.json()
  } catch {
    throw new ApiClientError("El servicio devolvió una respuesta inesperada. Intenta nuevamente.", "invalid-response", response.status)
  }
  if (!response.ok) {
    const detail = (payload as Partial<BackendErrorResponse>)?.detail
    throw new ApiClientError(
      typeof detail === "string" && detail.trim() ? detail : "No fue posible completar la solicitud. Intenta nuevamente.",
      "http",
      response.status,
    )
  }
  return payload as T
}

export function createCopilotApiClient(baseUrl: string) {
  const normalizedBaseUrl = baseUrl.trim().replace(/\/$/, "")
  return {
    submitQuery: (payload: CopilotQueryRequest) =>
      request<CopilotQueryResponse>(normalizedBaseUrl, "/copilot/query", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    getDateRange: () =>
      request<CopilotDateRange>(normalizedBaseUrl, "/copilot/date-range"),
    getHistory: (startDate: string, endDate: string) => {
      const params = new URLSearchParams({ start_date: startDate, end_date: endDate })
      return request<CopilotHistoryResponse>(
        normalizedBaseUrl,
        `/copilot/history?${params.toString()}`,
      )
    },
  }
}

const defaultClient = createCopilotApiClient(API_BASE_URL)

export const submitCopilotQuery = defaultClient.submitQuery
export const getCopilotDateRange = defaultClient.getDateRange
export const getCopilotHistory = defaultClient.getHistory
