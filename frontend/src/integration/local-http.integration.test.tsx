import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"

import App from "../App"
import {
  ApiClientError,
  createCopilotApiClient,
  getCopilotDateRange,
  getCopilotHistory,
  submitCopilotQuery,
} from "../services/api"
import type {
  CopilotDateRange,
  CopilotHistoryResponse,
  CopilotQueryResponse,
} from "../types/api"


function assertQueryContract(response: CopilotQueryResponse) {
  expect(response.question).toEqual(expect.any(String))
  expect(response.intent).toEqual(
    expect.objectContaining({
      is_valid: expect.any(Boolean),
      fecha_inicio: expect.any(String),
      fecha_fin: expect.any(String),
      monto: expect.any(Number),
    }),
  )
  expect(response.result.detalle).toEqual(
    expect.objectContaining({
      monto_actualizado: expect.any(Number),
      inflacion_pct: expect.any(Number),
      inpc_inicio: expect.any(Number),
      inpc_fin: expect.any(Number),
    }),
  )
  expect(response.history).toEqual(
    expect.arrayContaining([
      expect.objectContaining({ date: expect.any(String), inpc: expect.any(Number) }),
    ]),
  )
}


describe("React to FastAPI local HTTP integration", () => {
  it("loads the available date range through the running FastAPI server", async () => {
    const range: CopilotDateRange = await getCopilotDateRange()
    expect(range).toEqual({
      min_date: "2000-01-01",
      max_date: "2026-02-01",
      indicator: "INPC - General",
      source: "INEGI / BigQuery",
    })

    render(<App />)
    expect(await screen.findByText(/ene 2000.*feb 2026/i)).toBeInTheDocument()
  })

  it("submits a valid query and renders the real HTTP response", async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.type(screen.getByLabelText(/escribe tu duda/i), "Consulta válida de inflación")
    await user.click(screen.getByRole("button", { name: /calcular/i }))

    expect(await screen.findByText(/tu cálculo de inflación/i)).toBeInTheDocument()
    expect((await screen.findAllByText(/\$1,000\.00/)).length).toBeGreaterThan(0)
    expect(screen.getByRole("img", { name: /evolución histórica/i })).toBeInTheDocument()

    const response = await submitCopilotQuery({ question: "Consulta válida de inflación" })
    assertQueryContract(response)
  })

  it("shows a domain rejection returned by FastAPI", async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.type(screen.getByLabelText(/escribe tu duda/i), "Consulta rechazada")
    await user.click(screen.getByRole("button", { name: /calcular/i }))

    const alert = await screen.findByRole("alert")
    expect(alert).toHaveTextContent(/revisa tu consulta/i)
    expect(alert).toHaveTextContent(/solo puedo responder sobre inflación/i)
  })

  it("receives an ordered and JSON-serializable history contract", async () => {
    const response: CopilotHistoryResponse = await getCopilotHistory(
      "2020-01-01",
      "2024-01-01",
    )
    expect(response.history.map((point) => point.date)).toEqual([
      "2020-01-01T00:00:00",
      "2022-01-01T00:00:00",
      "2024-01-01T00:00:00",
    ])
    expect(JSON.parse(JSON.stringify(response))).toEqual(response)
  })

  it("renders a successful calculation when the comment is absent", async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.type(screen.getByLabelText(/escribe tu duda/i), "Consulta válida sin comentario")
    await user.click(screen.getByRole("button", { name: /calcular/i }))

    expect(await screen.findByText(/no se generó un comentario analítico/i)).toBeInTheDocument()
    expect(screen.getByText(/tu cálculo de inflación/i)).toBeInTheDocument()
  })

  it("maps a controlled backend error without exposing internal details", async () => {
    await expect(
      submitCopilotQuery({ question: "Provocar error interno" }),
    ).rejects.toMatchObject({
      kind: "http",
      status: 502,
      message: "No se pudo procesar la consulta en este momento.",
    })

    try {
      await submitCopilotQuery({ question: "Provocar error interno" })
    } catch (error) {
      expect(error).toBeInstanceOf(ApiClientError)
      expect(String(error)).not.toContain("credencial-interna")
    }
  })

  it("reports an unavailable backend as a network error", async () => {
    const unavailableClient = createCopilotApiClient("http://127.0.0.1:65534")
    await expect(unavailableClient.getDateRange()).rejects.toMatchObject({
      kind: "network",
      message: expect.stringMatching(/no pudimos comunicarnos/i),
    })
  })
})
