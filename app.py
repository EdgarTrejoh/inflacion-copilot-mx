import streamlit as st
import plotly.express as px
from datetime import datetime
from inflacion_service import procesar_pregunta_inflacion


# =========================
# UTILIDADES UI
# =========================
def formatear_fecha_corta(fecha_str: str) -> str:
    meses = {
        1: "ene", 2: "feb", 3: "mar", 4: "abr", 5: "may", 6: "jun",
        7: "jul", 8: "ago", 9: "sep", 10: "oct", 11: "nov", 12: "dic"
    }
    dt = datetime.strptime(fecha_str, "%Y-%m-%d")
    return f"{meses[dt.month]} {dt.year}"


# =========================
# CONFIGURACIÓN DE PÁGINA
# =========================
st.set_page_config(
    page_title="Inflación Copilot MX",
    page_icon="📈",
    layout="centered",
)

# =========================
# ENCABEZADO
# =========================
st.title("📈 Inflación Copilot MX")
st.subheader("Calcula la pérdida de poder adquisitivo con datos oficiales")

with st.expander("ℹ️ Instrucciones"):
    st.write(
        "Puedes escribir consultas como estas:\n"
        "- ¿A cuánto equivalen 1,000 pesos de enero de 2020 a enero de 2026?\n"
        "- ¿Qué poder adquisitivo tienen 500 pesos de junio de 2021 a diciembre de 2025?\n"
        "- ¿Cuánta inflación acumulada hubo de enero de 2022 a enero de 2024?"
    )

# =========================
# INPUT USUARIO
# =========================
pregunta = st.text_input(
    "Escribe tu duda aquí:",
    placeholder="Ej. ¿A cuánto equivalen 1,000 pesos de enero de 2020 a enero de 2026?"
)

# =========================
# BOTÓN PRINCIPAL
# =========================
if st.button("Calcular", use_container_width=True):

    if not pregunta.strip():
        st.error("Por favor, escribe una pregunta primero.")

    elif len(pregunta.strip()) < 10:
        st.warning("Escribe una consulta un poco más específica.")

    else:
        with st.spinner("Analizando datos económicos..."):
            salida = procesar_pregunta_inflacion(pregunta.strip())

        intencion = salida["intencion"]
        resultado = salida["resultado"]
        historico = salida["historico"]
        comentario = salida["comentario_analitico"]

        if not intencion.get("is_valid"):
            st.warning(intencion.get("respuesta_rechazo", "Consulta no válida."))

        elif not resultado["ok"]:
            st.error(resultado["mensaje"])

        else:
            detalle = resultado["detalle"]

            st.success("Cálculo realizado con datos oficiales del INEGI.")
            st.divider()

            # =========================
            # MÉTRICAS PRINCIPALES
            # =========================
            c1, c2 = st.columns(2)
            c1.metric(
                "Monto final equivalente",
                f"${detalle['monto_actualizado']:,.2f} MXN"
            )
            c2.metric(
                "Inflación acumulada",
                f"{detalle['inflacion_pct']:.2f}%"
            )

            c3, c4 = st.columns(2)
            c3.metric("INPC inicio", f"{detalle['inpc_inicio']:.2f}")
            c4.metric("INPC fin", f"{detalle['inpc_fin']:.2f}")

            # =========================
            # RESUMEN
            # =========================
            st.markdown("### Resumen")
            st.write(
                f"**${detalle['monto_inicial']:,.2f} MXN** de "
                f"**{formatear_fecha_corta(detalle['fecha_inicio'])}** "
                f"equivalen a **${detalle['monto_actualizado']:,.2f} MXN** en "
                f"**{formatear_fecha_corta(detalle['fecha_fin'])}**."
            )

            # =========================
            # GRÁFICA
            # =========================
            if historico is not None and not historico.empty:
                st.markdown("### 📉 Evolución histórica del INPC")
                df_plot = historico.sort_values("Fecha").copy()

                fig = px.line(
                    df_plot,
                    x="Fecha",
                    y="INPC",
                    markers=False,
                    title=None
                )

                # Eje Y iniciando en base 100
                y_max = df_plot["INPC"].max()
                fig.update_yaxes(range=[100, y_max * 1.02])

                # Línea base en 100 (referencia visual)
                fig.add_hline(
                    y=100,
                    line_dash="dot",
                    line_color="gray"
                )

                # Estética limpia tipo dashboard
                fig.update_layout(
                    margin=dict(l=10, r=10, t=10, b=10),
                    hovermode="x unified",
                    xaxis_title=None,
                    yaxis_title="INPC",
                )

                st.plotly_chart(fig, use_container_width=True)

                with st.expander("Ver histórico de datos"):
                    df_show = historico.copy()
                    df_show["INPC"] = df_show["INPC"].round(2)
                    st.dataframe(df_show, use_container_width=True)

            # =========================
            # ANÁLISIS IA
            # =========================
            if comentario:
                st.markdown("### 🤖 Lectura analítica")
                st.info(comentario) 