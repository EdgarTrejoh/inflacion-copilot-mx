import { useEffect, useState } from "react"
import { QueryForm } from "./components/QueryForm"
import { ResultsPanel } from "./components/ResultsPanel"
import { StatusMessage } from "./components/StatusMessage"
import { ApiClientError, getCopilotDateRange, getCopilotHistory, submitCopilotQuery } from "./services/api"
import type { CopilotDateRange, CopilotQueryResponse } from "./types/api"
import { formatDate } from "./utils/format"

type PageStatus = "idle" | "submitting" | "success" | "error"

function friendlyError(error: unknown) {
  if (error instanceof ApiClientError) {
    if (error.kind === "network") return { title: "Sin conexión con el servicio", message: error.message }
    if (error.status === 400) return { title: "Revisa tu consulta", message: error.message }
    if (error.status === 404) return { title: "Datos no disponibles", message: error.message }
    return { title: "No pudimos completar el cálculo", message: error.message }
  }
  return { title: "Ocurrió un inconveniente", message: "No fue posible completar la consulta. Intenta nuevamente en unos momentos." }
}

export default function App() {
  const [question, setQuestion] = useState("")
  const [dateRange, setDateRange] = useState<CopilotDateRange | null>(null)
  const [isRangeLoading, setIsRangeLoading] = useState(true)
  const [rangeUnavailable, setRangeUnavailable] = useState(false)
  const [status, setStatus] = useState<PageStatus>("idle")
  const [response, setResponse] = useState<CopilotQueryResponse | null>(null)
  const [error, setError] = useState<{ title: string; message: string } | null>(null)

  useEffect(() => {
    let active = true
    getCopilotDateRange().then((range) => { if (active) setDateRange(range) })
      .catch(() => { if (active) setRangeUnavailable(true) })
      .finally(() => { if (active) setIsRangeLoading(false) })
    return () => { active = false }
  }, [])

  async function handleSubmit() {
    const normalized = question.trim()
    if (!normalized) {
      setResponse(null); setStatus("error")
      setError({ title: "Escribe una pregunta", message: "Cuéntanos qué monto y periodos quieres comparar." })
      return
    }
    setStatus("submitting"); setError(null); setResponse(null)
    try {
      const result = await submitCopilotQuery({ question: normalized })
      if (!result.history.length && result.intent.fecha_inicio && result.intent.fecha_fin) {
        try {
          const history = await getCopilotHistory(result.intent.fecha_inicio, result.intent.fecha_fin)
          result.history = history.history
        } catch { /* The calculation remains useful without optional history. */ }
      }
      setResponse(result); setStatus("success")
    } catch (caught) {
      setError(friendlyError(caught)); setStatus("error")
    }
  }

  return <div className="app-shell">
    <header className="site-header"><a className="brand" href="#main-content" aria-label="Inflación Copilot MX, ir al contenido principal"><span className="brand__mark" aria-hidden="true">MX</span><span>Inflación Copilot</span></a><span className="official-data">Datos oficiales de México</span></header>
    <main id="main-content">
      <section className="hero" aria-labelledby="page-title"><div className="hero__copy"><span className="eyebrow">Educación económica clara</span><h1 id="page-title">Entiende cuánto ha cambiado el valor de tu dinero.</h1><p>Pregunta con tus propias palabras y calcula el efecto de la inflación usando el Índice Nacional de Precios al Consumidor.</p></div>
        <div className="range-card" aria-live="polite"><span>Información disponible</span>{isRangeLoading && <strong>Cargando rango…</strong>}{!isRangeLoading && dateRange && <strong>{formatDate(dateRange.min_date)} — {formatDate(dateRange.max_date)}</strong>}{!isRangeLoading && rangeUnavailable && <strong>El rango se confirmará al calcular</strong>}<small>Fuente: INEGI · INPC general</small></div>
      </section>
      <section className="query-card" aria-labelledby="query-title"><div className="query-card__heading"><span className="step-number" aria-hidden="true">01</span><div><h2 id="query-title">Haz una consulta</h2><p>Por ejemplo: “¿A cuánto equivalen $500 de junio de 2021 a diciembre de 2025?”</p></div></div>
        <QueryForm question={question} isSubmitting={status === "submitting"} onQuestionChange={setQuestion} onSubmit={handleSubmit}/>
      </section>
      {status === "submitting" && <StatusMessage tone="info" title="Analizando tu consulta">Estamos interpretando las fechas y consultando los datos oficiales.</StatusMessage>}
      {status === "error" && error && <StatusMessage tone="error" title={error.title} live="assertive">{error.message}</StatusMessage>}
      {status === "success" && response && <ResultsPanel response={response}/>}
      <section className="trust-strip" aria-label="Cómo funciona"><div><strong>01</strong><span>Interpretamos tu pregunta</span></div><div><strong>02</strong><span>Consultamos el INPC oficial</span></div><div><strong>03</strong><span>Explicamos el resultado</span></div></section>
    </main>
    <footer><span>Inflación Copilot MX</span><span>Una herramienta educativa basada en datos oficiales.</span></footer>
  </div>
}
