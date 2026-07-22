import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import App from "./App"
import { ApiClientError, getCopilotDateRange, getCopilotHistory, submitCopilotQuery } from "./services/api"
import { dateRange, successfulResponse } from "./test/fixtures"

vi.mock("./services/api", async (original) => {
  const actual = await original<typeof import("./services/api")>()
  return { ...actual, getCopilotDateRange: vi.fn(), getCopilotHistory: vi.fn(), submitCopilotQuery: vi.fn() }
})

const mockRange = vi.mocked(getCopilotDateRange)
const mockHistory = vi.mocked(getCopilotHistory)
const mockSubmit = vi.mocked(submitCopilotQuery)

beforeEach(() => {
  vi.clearAllMocks()
  mockRange.mockResolvedValue(dateRange)
  mockHistory.mockResolvedValue({ ...dateRange, start_date: dateRange.min_date, end_date: dateRange.max_date, history: [] })
})

describe("Inflación Copilot", () => {
  it("renders the initial experience and available date range", async () => {
    render(<App />)
    expect(screen.getByRole("heading", { name: /entiende cuánto/i })).toBeInTheDocument()
    expect(screen.getByLabelText(/escribe tu duda/i)).toBeInTheDocument()
    expect(screen.getByText(/cargando rango/i)).toBeInTheDocument()
    expect(await screen.findByText(/ene 2000.*feb 2026/i)).toBeInTheDocument()
  })

  it("captures and submits a natural-language question", async () => {
    mockSubmit.mockResolvedValue(successfulResponse())
    const user = userEvent.setup(); render(<App />)
    const input = screen.getByLabelText(/escribe tu duda/i)
    await user.type(input, "¿A cuánto equivalen 800 pesos de 2020 a 2024?")
    await user.click(screen.getByRole("button", { name: /calcular/i }))
    await waitFor(() => expect(mockSubmit).toHaveBeenCalledWith({ question: "¿A cuánto equivalen 800 pesos de 2020 a 2024?" }))
  })

  it("shows a clear loading state while the query is pending", async () => {
    let resolveQuery!: (value: ReturnType<typeof successfulResponse>) => void
    mockSubmit.mockReturnValue(new Promise((resolve) => { resolveQuery = resolve }))
    const user = userEvent.setup(); render(<App />)
    await user.type(screen.getByLabelText(/escribe tu duda/i), "Consulta de inflación válida")
    await user.click(screen.getByRole("button", { name: /calcular/i }))
    expect(screen.getByText(/analizando tu consulta/i)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /calculando/i })).toBeDisabled()
    resolveQuery(successfulResponse())
    expect(await screen.findByText(/tu cálculo de inflación/i)).toBeInTheDocument()
  })

  it("renders the complete result with formatted money, percentages, chart and table", async () => {
    mockSubmit.mockResolvedValue(successfulResponse())
    const user = userEvent.setup(); render(<App />)
    await user.type(screen.getByLabelText(/escribe tu duda/i), "Consulta completa")
    await user.click(screen.getByRole("button", { name: /calcular/i }))
    expect((await screen.findAllByText(/\$1,000\.00/)).length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText("25.00%")).toBeInTheDocument()
    expect(screen.getAllByText("100.00").length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText("125.00").length).toBeGreaterThanOrEqual(1)
    expect(screen.getByRole("img", { name: /evolución histórica/i })).toBeInTheDocument()
    expect(screen.getByText(/ver histórico de datos \(2\)/i)).toBeInTheDocument()
    expect(screen.getByText(/perdió poder adquisitivo/i)).toBeInTheDocument()
  })

  it("validates an empty question without calling the API", async () => {
    const user = userEvent.setup(); render(<App />)
    await user.click(screen.getByRole("button", { name: /calcular/i }))
    expect(screen.getByRole("alert")).toHaveTextContent(/escribe una pregunta/i)
    expect(mockSubmit).not.toHaveBeenCalled()
  })

  it("shows a controlled rejection or validation message", async () => {
    mockSubmit.mockRejectedValue(new ApiClientError("Solo puedo responder sobre inflación en México.", "http", 400))
    const user = userEvent.setup(); render(<App />)
    await user.type(screen.getByLabelText(/escribe tu duda/i), "¿Quién ganó el partido?")
    await user.click(screen.getByRole("button", { name: /calcular/i }))
    expect(await screen.findByRole("alert")).toHaveTextContent(/revisa tu consulta/i)
    expect(screen.getByRole("alert")).toHaveTextContent(/solo puedo responder sobre inflación/i)
  })

  it("shows a controlled HTTP error", async () => {
    mockSubmit.mockRejectedValue(new ApiClientError("No se pudo procesar la consulta en este momento.", "http", 502))
    const user = userEvent.setup(); render(<App />)
    await user.type(screen.getByLabelText(/escribe tu duda/i), "Consulta válida")
    await user.click(screen.getByRole("button", { name: /calcular/i }))
    expect(await screen.findByRole("alert")).toHaveTextContent(/no pudimos completar el cálculo/i)
    expect(screen.getByRole("alert")).not.toHaveTextContent(/cloud run|bigquery|vertex/i)
  })

  it("shows a friendly network error", async () => {
    mockSubmit.mockRejectedValue(new ApiClientError("No pudimos comunicarnos con el servicio.", "network"))
    const user = userEvent.setup(); render(<App />)
    await user.type(screen.getByLabelText(/escribe tu duda/i), "Consulta válida")
    await user.click(screen.getByRole("button", { name: /calcular/i }))
    expect(await screen.findByRole("alert")).toHaveTextContent(/sin conexión con el servicio/i)
  })

  it("tries the history endpoint and handles an empty history", async () => {
    const result = successfulResponse(); result.history = []
    mockSubmit.mockResolvedValue(result)
    const user = userEvent.setup(); render(<App />)
    await user.type(screen.getByLabelText(/escribe tu duda/i), "Consulta sin histórico")
    await user.click(screen.getByRole("button", { name: /calcular/i }))
    expect(await screen.findByText(/histórico no disponible/i)).toBeInTheDocument()
    expect(mockHistory).toHaveBeenCalledWith("2020-01-01", "2024-01-01")
  })

  it("handles an absent analytical comment", async () => {
    const result = successfulResponse(); result.analytical_comment = null
    mockSubmit.mockResolvedValue(result)
    const user = userEvent.setup(); render(<App />)
    await user.type(screen.getByLabelText(/escribe tu duda/i), "Consulta sin comentario")
    await user.click(screen.getByRole("button", { name: /calcular/i }))
    expect(await screen.findByText(/no se generó un comentario analítico/i)).toBeInTheDocument()
  })
})
