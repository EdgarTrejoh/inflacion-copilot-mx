import type { FormEvent } from "react"

interface Props { question: string; isSubmitting: boolean; onQuestionChange: (value: string) => void; onSubmit: () => void }

export function QueryForm({ question, isSubmitting, onQuestionChange, onSubmit }: Props) {
  const handleSubmit = (event: FormEvent) => { event.preventDefault(); onSubmit() }
  return <form className="query-form" onSubmit={handleSubmit} noValidate>
    <label htmlFor="inflation-question">Escribe tu duda</label>
    <div className="query-form__controls">
      <input id="inflation-question" value={question} disabled={isSubmitting} autoComplete="off"
        onChange={(event) => onQuestionChange(event.target.value)} aria-describedby="query-help"
        placeholder="Ej. ¿A cuánto equivalen $1,000 de enero de 2020 a enero de 2026?" />
      <button type="submit" disabled={isSubmitting}>{isSubmitting ? "Calculando…" : "Calcular"}</button>
    </div>
    <p id="query-help" className="query-form__help">Incluye un monto y dos periodos. Si omites el monto, calcularemos sobre $1 MXN.</p>
  </form>
}
