# Frontend React

Interfaz productiva de Inflación Copilot MX construida con React, TypeScript y Vite. Consume exclusivamente los contratos conversacionales de FastAPI; el navegador no accede directamente a BigQuery ni Vertex AI.

La arquitectura general y la operación productiva están documentadas en el [README principal](../README.md) y en [PRODUCTION_OPERATIONS.md](../deployment/PRODUCTION_OPERATIONS.md).

## Desarrollo local

Inicia primero el backend desde la raíz del repositorio:

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.main:app --reload --port 8020
```

Después prepara y ejecuta el frontend:

```powershell
cd frontend
Copy-Item .env.example .env.local
npm ci
npm run dev
```

Vite muestra la URL al iniciar; normalmente es `http://localhost:5173`.

## Variables de entorno

`VITE_API_BASE_URL` define el prefijo del cliente HTTP centralizado en `src/services/api.ts`.

Desarrollo con FastAPI local:

```env
VITE_API_BASE_URL=http://127.0.0.1:8020
```

Producción y beta con Firebase Hosting:

```env
VITE_API_BASE_URL=/api
```

La URL no se configura dentro de los componentes. Si la variable está ausente, el cliente utiliza `/api` como valor predeterminado.

## Contratos consumidos

El frontend llama:

- `POST /copilot/query`;
- `GET /copilot/date-range`;
- `GET /copilot/history`.

Con `VITE_API_BASE_URL=/api`, las rutas resultantes son `/api/copilot/**`. Firebase las reescribe al servicio FastAPI correspondiente.

Los tipos de solicitudes, respuestas, históricos y errores se encuentran en `src/types/api.ts`. TypeScript los verifica durante compilación y pruebas; actualmente no existe validación de respuestas en runtime mediante un esquema.

## Componentes principales

| Archivo | Responsabilidad |
|---|---|
| `src/App.tsx` | Estado de página, rango inicial, consultas y errores |
| `src/components/QueryForm.tsx` | Captura y envío de la pregunta |
| `src/components/ResultsPanel.tsx` | Resumen, métricas, histórico y comentario |
| `src/components/MetricCard.tsx` | Monto, inflación e INPC |
| `src/components/InflationChart.tsx` | Gráfica SVG responsiva |
| `src/components/HistoryTable.tsx` | Tabla accesible del histórico |
| `src/components/StatusMessage.tsx` | Estados de carga y error |
| `src/services/api.ts` | Cliente HTTP y normalización de errores |
| `src/utils/format.ts` | Formato de fechas, montos y porcentajes |

La gráfica utiliza SVG nativo y ordena la serie recibida. No incorpora una biblioteca externa de visualización.

## Estados y manejo de errores

La interfaz contempla:

- carga inicial del rango disponible;
- pregunta vacía;
- consulta en proceso;
- resultado completo;
- rechazo fuera de dominio;
- error de validación o datos ausentes;
- error HTTP o de red;
- respuesta no JSON;
- histórico vacío;
- comentario analítico ausente.

Los errores se presentan con mensajes orientados a la persona usuaria y no muestran trazas ni detalles de infraestructura.

El frontend no utiliza WebSocket, EventSource ni polling. Sólo solicita el rango al montar la aplicación y realiza nuevas llamadas cuando la persona envía una consulta o cuando necesita recuperar un histórico ausente.

## Pruebas

```powershell
cd frontend
npm test
npm run test:integration
npm run build
```

- `npm test`: componentes, formatos, estados y cliente HTTP con mocks.
- `npm run test:integration`: HTTP real contra una aplicación FastAPI temporal; BigQuery y Vertex AI permanecen sustituidos.
- `npm run build`: compilación TypeScript y build Vite.

## Build y preview

Para probar un build contra el backend local:

```powershell
cd frontend
$env:VITE_API_BASE_URL="http://127.0.0.1:8020"
npm run build
npx vite preview --host 127.0.0.1 --port 5173
```

Actualmente no existe un script `npm run preview` en `package.json`. Usa `npx vite preview` hasta que el repositorio incorpore explícitamente ese script.

Para Firebase, el build se genera con `VITE_API_BASE_URL=/api`; `firebase.production.json` y `firebase.beta.json` determinan a qué servicio Cloud Run se reescribe el tráfico.
