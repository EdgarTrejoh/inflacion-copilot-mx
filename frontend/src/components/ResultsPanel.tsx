import type { CopilotQueryResponse } from "../types/api"
import { formatCurrency, formatDate, formatPercentage, numberFormatter } from "../utils/format"
import { HistoryTable } from "./HistoryTable"
import { InflationChart } from "./InflationChart"
import { MetricCard } from "./MetricCard"
import { StatusMessage } from "./StatusMessage"

export function ResultsPanel({ response }: { response: CopilotQueryResponse }) {
  const detail = response.result.detalle
  if (!detail) return null
  return <section className="results" aria-labelledby="results-title">
    <div className="results__heading"><div><span className="eyebrow">Resultado con datos oficiales</span><h2 id="results-title">Tu cálculo de inflación</h2></div><span className="source-pill">INEGI · INPC</span></div>
    <div className="metrics-grid">
      <MetricCard label="Monto final equivalente" value={formatCurrency(detail.monto_actualizado)} featured />
      <MetricCard label="Inflación acumulada" value={formatPercentage(detail.inflacion_pct)} featured />
      <MetricCard label="INPC inicial" value={numberFormatter.format(detail.inpc_inicio)} />
      <MetricCard label="INPC final" value={numberFormatter.format(detail.inpc_fin)} />
    </div>
    <div className="summary-card"><h3>Resumen</h3><p><strong>{formatCurrency(detail.monto_inicial)}</strong> de {formatDate(detail.fecha_inicio)} equivalen a <strong>{formatCurrency(detail.monto_actualizado)}</strong> en {formatDate(detail.fecha_fin)}.</p></div>
    <section className="data-section" aria-labelledby="history-title"><span className="eyebrow">Serie oficial</span><h3 id="history-title">Evolución histórica del INPC</h3>
      {response.history.length ? <><InflationChart history={response.history}/><HistoryTable history={response.history}/></> :
        <StatusMessage tone="info" title="Histórico no disponible">El cálculo está listo, pero no recibimos la serie histórica para este periodo.</StatusMessage>}
    </section>
    <section className="analysis-card" aria-labelledby="analysis-title"><span className="analysis-card__mark" aria-hidden="true">IA</span><div><h3 id="analysis-title">Lectura analítica</h3>
      {response.analytical_comment ? <p>{response.analytical_comment}</p> : <p className="muted">El cálculo está disponible, pero no se generó un comentario analítico.</p>}</div></section>
  </section>
}
