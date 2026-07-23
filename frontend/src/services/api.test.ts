import { afterEach, describe, expect, it, vi } from "vitest"
import { ApiClientError, getCopilotDateRange, getCopilotHistory, submitCopilotQuery } from "./api"
import { dateRange, successfulResponse } from "../test/fixtures"

afterEach(() => vi.restoreAllMocks())
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } })

describe("copilot API client", () => {
  it("posts a typed query only to /copilot/query", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(response(successfulResponse()))
    await expect(submitCopilotQuery({ question: "Consulta" })).resolves.toEqual(successfulResponse())
    expect(fetchMock).toHaveBeenCalledWith(expect.stringMatching(/\/copilot\/query$/), expect.objectContaining({ method: "POST", body: JSON.stringify({ question: "Consulta" }) }))
  })

  it("gets typed date-range metadata", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(response(dateRange))
    await expect(getCopilotDateRange()).resolves.toEqual(dateRange)
    expect(fetchMock).toHaveBeenCalledWith(expect.stringMatching(/\/copilot\/date-range$/), expect.anything())
  })

  it("encodes history query parameters", async () => {
    const payload = { ...dateRange, start_date: "2020-01-01", end_date: "2024-01-01", history: [] }
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(response(payload))
    await getCopilotHistory("2020-01-01", "2024-01-01")
    expect(fetchMock.mock.calls[0][0]).toMatch(/\/copilot\/history\?start_date=2020-01-01&end_date=2024-01-01$/)
  })

  it("maps controlled HTTP errors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(response({ detail: "Consulta fuera de dominio." }, 400))
    await expect(submitCopilotQuery({ question: "Otro tema" })).rejects.toMatchObject({ kind: "http", status: 400, message: "Consulta fuera de dominio." } satisfies Partial<ApiClientError>)
  })

  it("maps network failures without leaking technical details", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("ECONNREFUSED internal-host"))
    await expect(getCopilotDateRange()).rejects.toMatchObject({ kind: "network", message: expect.not.stringContaining("internal-host") })
  })
})
