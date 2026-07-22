interface Props { label: string; value: string; featured?: boolean }
export function MetricCard({ label, value, featured = false }: Props) {
  return <article className={`metric-card${featured ? " metric-card--featured" : ""}`}><span>{label}</span><strong>{value}</strong></article>
}
