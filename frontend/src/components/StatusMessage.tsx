import type { ReactNode } from "react"

interface Props { tone: "info" | "error" | "success"; title: string; children: ReactNode; live?: "polite" | "assertive" }

export function StatusMessage({ tone, title, children, live = "polite" }: Props) {
  return <div className={`status status--${tone}`} role={tone === "error" ? "alert" : "status"} aria-live={live}>
    <strong>{title}</strong><span>{children}</span>
  </div>
}
