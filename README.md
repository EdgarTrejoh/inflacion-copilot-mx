<div align="center">

# 📈 Inflación Copilot MX

**Plataforma conversacional para analizar poder adquisitivo en México**  
con lenguaje natural, datos oficiales e IA responsable.

[![Estado](https://img.shields.io/badge/estado-MVP%20en%20producción-brightgreen?style=flat-square)](https://github.com/tu-usuario/inflacion-copilot-mx)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.x-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)](https://streamlit.io)
[![Google Cloud](https://img.shields.io/badge/Google%20Cloud-BigQuery%20%7C%20Vertex%20AI-4285F4?style=flat-square&logo=google-cloud&logoColor=white)](https://cloud.google.com)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docker.com)
[![Licencia](https://img.shields.io/badge/licencia-MIT-blue?style=flat-square)](LICENSE)
[![Google AI Essentials](https://img.shields.io/badge/Google%20AI%20Essentials-AI%20Applied%20Challenge-orange?style=flat-square&logo=google)](https://grow.google)

> No es un chatbot. Es un **copiloto analítico**.

</div>

---

## 🎯 ¿Qué es Inflación Copilot MX?

Inflación Copilot MX permite que cualquier persona consulte, calcule y entienda el impacto de la inflación en México de forma clara y confiable.

Convierte preguntas en lenguaje natural en cálculos económicos precisos, visualizaciones interactivas e interpretaciones basadas en datos oficiales del INEGI.

**Ejemplo de consulta:**

```
¿A cuánto equivalen $100 pesos de 2020 en 2024?
```

---

## 🚀 Funcionalidades

- Consultar inflación acumulada entre dos periodos
- Calcular equivalencias de poder adquisitivo históricas
- Visualizar la evolución del INPC
- Obtener interpretación económica automática
- Usar lenguaje natural como interfaz analítica

---

## 🧠 Diferenciadores clave

| Característica | Descripción |
|---|---|
| **Dominio acotado** | Solo inflación y poder adquisitivo en México |
| **IA con guardrails** | Valida intención semántica antes de responder |
| **Datos curados** | Fuente única: API oficial del INEGI |
| **Automatización total** | Pipeline ETL sin intervención manual |
| **Arquitectura empresarial** | Infraestructura cloud productiva en GCP |

---

## 🏛️ Fuente de Datos

**INEGI — API Oficial de Indicadores**

✔ Sin scraping · ✔ Sin intermediarios · ✔ Trazabilidad completa

---

## ☁️ Arquitectura del Sistema

### Flujo de consulta

```mermaid
flowchart TD
    A[👤 Usuario] --> B[Streamlit · UI Conversacional]
    B --> C[Vertex AI · Gemini 2.5 Flash]
    C --> D[(BigQuery · Datos Oficiales)]
    D --> E[Resultados + Visualización + Lectura Analítica]
    E --> A
```

### Pipeline ETL automatizado

```mermaid
flowchart LR
    A[Cloud Scheduler\ncron mensual] --> B[Cloud Run\nservicio ETL Python]
    B --> C[INEGI API]
    C --> D[ETL\nNormalización]
    D --> E[(BigQuery\ninflacion_historica)]
```

---

## 🗄️ Modelo de Datos

**Dataset:** `datos_economicos_mx` · **Tabla:** `inflacion_historica`

| Campo | Tipo | Descripción |
|---|---|---|
| `fecha` | TIMESTAMP | Fecha del registro |
| `periodo` | STRING | Formato YYYY/MM |
| `valor_inpc` | FLOAT | Índice INPC |
| `tipo` | STRING | General / Subyacente / No subyacente |
| `procesado_en` | TIMESTAMP | Timestamp de carga |
| `fuente` | STRING | `API_INEGI` |

---

## 🤖 IA Responsable por Diseño

Antes de cualquier cálculo, el agente:

1. Interpreta la intención semántica de la consulta
2. Valida relevancia al dominio de inflación
3. Restringe fechas fuera del rango disponible
4. Rechaza solicitudes fuera de contexto
5. Usa únicamente fuentes oficiales verificables

| Tipo de consulta | Comportamiento |
|---|---|
| ✅ Válida | Calcula, visualiza y explica |
| ⚠️ Fuera de rango | Bloquea y notifica fechas válidas |
| 🚫 Fuera de dominio | Rechaza con mensaje claro |

---

## 🧩 Stack Tecnológico

| Capa | Tecnología |
|---|---|
| Frontend | Streamlit |
| IA Generativa | Google Vertex AI — Gemini 2.5 Flash |
| Base de Datos | Google BigQuery |
| Orquestación ETL | Cloud Scheduler + Cloud Run |
| Contenerización | Docker |
| Lenguaje | Python 3.12 |

---

## 📦 Instalación Local

```bash
git clone https://github.com/tu-usuario/inflacion-copilot-mx.git
cd inflacion-copilot-mx
pip install -r requirements.txt
```

### Configuración del Entorno (`.env`)

Crea un archivo `.env` en la raíz del proyecto para definir las credenciales:

```env
GCP_PROJECT_ID="tu-proyecto-gcp"
GCP_LOCATION="us-central1"
GCP_TABLE_ID="tu-proyecto-gcp.datos_economicos_mx.inflacion_historica"
```

### Configuración de Fechas (`config.py`)

Las fechas máximas y mínimas de consulta están definidas en `config.py`. Ajusta `MIN_DATE` y `MAX_DATE` de ser necesario (la plataforma soporta cálculos hasta el **1 de febrero de 2026**).

### Correr la Aplicación

```bash
streamlit run app.py
```

### Correr la API REST local

La API FastAPI expone calculos estructurados de inflacion acumulada para consumo de otros servicios. Este modo no usa IA generativa, Gemini, Vertex AI ni clasificacion de intencion; solo consulta INPC en BigQuery y calcula:

```text
inflation_pct = ((inpc_end / inpc_start) - 1) * 100
```

La UI conversacional de Streamlit sigue funcionando en `app.py` como experiencia separada.

```bash
uvicorn api.main:app --reload --port 8020
```

#### `GET /health`

```bash
curl http://127.0.0.1:8020/health
```

Respuesta:

```json
{
  "status": "ok",
  "service": "inflacion-copilot-api"
}
```

#### `GET /inflation/period`

Consulta inflacion acumulada entre dos fechas con formato `YYYY-MM-DD`:

```bash
curl "http://127.0.0.1:8020/inflation/period?start_date=2024-01-01&end_date=2025-12-01"
```

Respuesta esperada:

```json
{
  "start_date": "2024-01-01",
  "end_date": "2025-12-01",
  "inpc_start": 133.555,
  "inpc_end": 140.123,
  "factor": 1.0491782415487993,
  "inflation_pct": 4.91782415487993,
  "source": "INEGI / BigQuery",
  "indicator": "INPC - General",
  "method": "inflation_pct = ((inpc_end / inpc_start) - 1) * 100"
}
```

Variables requeridas para la API:

```env
GCP_PROJECT_ID="tu-proyecto-gcp"
GCP_TABLE_ID="tu-proyecto-gcp.datos_economicos_mx.inflacion_historica"
```

`GCP_LOCATION` se mantiene para la app Streamlit con Vertex AI. La API no la requiere.

Esta API puede ser consumida posteriormente por `infonavit-strategic-report-api`; la integracion con INFONAVIT no forma parte de esta fase.

### Ejecutar Pruebas Automatizadas (Testing)

El proyecto cuenta con testing unitario implementado con `pytest`. Para correr la batería de pruebas:

```bash
pytest test_inflacion_service.py -v
```

Para correr toda la suite, incluyendo pruebas de API con mocks:

```bash
python -m pytest -q
```

## 🐳 Despliegue con Docker

Asegúrate de tener listo tu archivo `.env`.

```bash
docker build -t inflacion-app .
docker run --env-file .env -p 8080:8080 inflacion-app
```

El Dockerfile actual conserva el arranque productivo de Streamlit. Preparar una imagen o comando de despliegue para la API FastAPI queda como fase posterior para no romper el comportamiento existente.

---

## 🧪 Casos de Uso

Educación financiera · Consultoría económica · Presentaciones ejecutivas · Herramientas fintech · Análisis macroeconómico

---

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Por favor abre un *issue* para discutir cambios mayores antes de enviar un *pull request*.

---

## 📄 Licencia

Distribuido bajo licencia MIT.

---

<div align="center">

Desarrollado por **Edgar Trejo**  
como parte del programa **Google AI Essentials — AI Applied Challenge, Módulo 4**

*Implementa principios prácticos de IA Responsable: guardrails conversacionales, validación semántica de intención, restricción de dominio y trazabilidad de fuentes oficiales.*

</div>
