import type { HistoryPoint } from "../types/api"
import { formatDate, numberFormatter } from "../utils/format"

export function HistoryTable({ history }: { history: HistoryPoint[] }) {
  if (!history.length) return null
  const ordered = [...history].sort((a,b) => a.date.localeCompare(b.date))
  return <details className="history-details"><summary>Ver histórico de datos ({ordered.length})</summary><div className="table-wrap"><table>
    <caption className="sr-only">Valores históricos del Índice Nacional de Precios al Consumidor</caption>
    <thead><tr><th scope="col">Periodo</th><th scope="col">INPC</th></tr></thead>
    <tbody>{ordered.map((point) => <tr key={point.date}><td>{formatDate(point.date)}</td><td>{numberFormatter.format(point.inpc)}</td></tr>)}</tbody>
  </table></div></details>
}
