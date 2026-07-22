import { useId, useMemo, useState } from "react"
import type { HistoryPoint } from "../types/api"
import { formatDate, numberFormatter } from "../utils/format"

const W = 760, H = 300, L = 58, R = 24, T = 24, B = 48

export function InflationChart({ history }: { history: HistoryPoint[] }) {
  const titleId = useId(), descriptionId = useId()
  const [active, setActive] = useState<number | null>(null)
  const points = useMemo(() => [...history].sort((a, b) => a.date.localeCompare(b.date)), [history])
  if (!points.length) return <p className="empty-state">No hay histórico disponible para esta consulta.</p>
  const values = points.map((point) => point.inpc)
  const min = Math.min(...values), max = Math.max(...values), spread = max - min || Math.max(max * .02, 1)
  const yMin = min - spread * .12, yMax = max + spread * .12, cw = W - L - R, ch = H - T - B
  const x = (index: number) => L + (points.length === 1 ? cw / 2 : index / (points.length - 1) * cw)
  const y = (value: number) => T + (yMax - value) / (yMax - yMin) * ch
  const selected = active === null ? null : points[active]
  return <div className="chart-wrap"><svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-labelledby={`${titleId} ${descriptionId}`}>
    <title id={titleId}>Evolución histórica del INPC</title>
    <desc id={descriptionId}>Serie de {points.length} observaciones, desde {formatDate(points[0].date)} hasta {formatDate(points.at(-1)!.date)}.</desc>
    {[0, .5, 1].map((ratio) => { const value = yMax - ratio * (yMax - yMin), py = T + ratio * ch; return <g key={ratio}>
      <line className="chart__grid" x1={L} x2={W-R} y1={py} y2={py}/><text className="chart__axis-label" x={L-10} y={py+4} textAnchor="end">{numberFormatter.format(value)}</text>
    </g> })}
    <polyline className="chart__line" points={points.map((point, index) => `${x(index)},${y(point.inpc)}`).join(" ")} fill="none" />
    {points.map((point, index) => <circle key={`${point.date}-${index}`} className="chart__hit-area" cx={x(index)} cy={y(point.inpc)} r="12" tabIndex={0}
      aria-label={`${formatDate(point.date)}: INPC ${numberFormatter.format(point.inpc)}`}
      onMouseEnter={() => setActive(index)} onMouseLeave={() => setActive(null)} onFocus={() => setActive(index)} onBlur={() => setActive(null)} />)}
    <text className="chart__date-label" x={L} y={H-14}>{formatDate(points[0].date)}</text>
    <text className="chart__date-label" x={W-R} y={H-14} textAnchor="end">{formatDate(points.at(-1)!.date)}</text>
    {selected && active !== null && <g className="chart__tooltip" pointerEvents="none"><circle cx={x(active)} cy={y(selected.inpc)} r="5"/>
      <rect x={Math.min(x(active)+10,W-180)} y={Math.max(y(selected.inpc)-54,8)} width="158" height="44" rx="8"/>
      <text x={Math.min(x(active)+22,W-168)} y={Math.max(y(selected.inpc)-36,26)}>{formatDate(selected.date)}</text>
      <text x={Math.min(x(active)+22,W-168)} y={Math.max(y(selected.inpc)-20,42)}>INPC {numberFormatter.format(selected.inpc)}</text></g>}
  </svg></div>
}
