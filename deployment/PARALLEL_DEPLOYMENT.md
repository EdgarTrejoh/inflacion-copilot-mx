# Despliegue paralelo y operación beta

Esta guía documenta la beta desplegada y los comandos para reproducirla. No autoriza publicar Firebase `live`, modificar el servicio Streamlit ni promover la beta a producción.

## Arquitectura anterior

Streamlit sirve interfaz y lógica desde un proceso persistente en Cloud Run. Una pestaña abierta mantiene la sesión de Streamlit y puede prolongar el uso de CPU.

```text
Usuario → Cloud Run inflacion-copilot (Streamlit) → Gemini / BigQuery
```

## Arquitectura nueva en paralelo

```text
Usuario
  └─ Firebase Hosting (frontend/dist)
       ├─ archivos estáticos React
       ├─ rutas SPA → /index.html
       └─ /api/** → Cloud Run: inflacion-copilot-api-beta
                         ├─ FastAPI /api/copilot/**
                         ├─ Vertex AI / Gemini
                         └─ BigQuery / INPC

Rollback independiente: Cloud Run inflacion-copilot (Streamlit actual)
```

La estrategia elegida usa un mismo origen. El build productivo define `VITE_API_BASE_URL=/api`; Firebase reescribe `/api/**` hacia Cloud Run y FastAPI conserva también los contratos originales `/copilot/**`. Esto evita CORS en operación normal, pero CORS sigue disponible para desarrollo local o para una futura separación de dominios.

## Estado de la beta

- Proyecto: `fluted-oath-477301-c1`.
- Región: `us-central1`.
- Backend: `inflacion-copilot-api-beta`.
- Firebase: canal preview `react-beta`; el canal `live` permanece fuera de alcance.
- Cuenta de ejecución: `inflacion-copilot-api-beta@fluted-oath-477301-c1.iam.gserviceaccount.com`.
- Streamlit de respaldo: `inflacion-copilot`, sin cambios de imagen, IAM o tráfico.

## Variables

Backend:

- `GCP_PROJECT_ID`: proyecto que factura y accede a BigQuery/Vertex AI.
- `GCP_LOCATION`: región de Vertex AI y referencia de despliegue.
- `GCP_TABLE_ID`: identificador completo de la tabla de INPC.
- `COPILOT_ALLOWED_ORIGINS`: uno o varios orígenes separados por coma; no admite `*`.
- `PORT`: inyectada por Cloud Run; el contenedor usa `8080` sólo como valor local predeterminado.

Frontend:

- `VITE_API_BASE_URL`: `/api` para Firebase con mismo origen; URL absoluta para desarrollo o dominios separados.

No se almacenan credenciales ni secretos en el repositorio. Copiar `deployment/cloud-run.env.example.yaml` como `deployment/cloud-run.env.yaml` y sustituir sus marcadores; el archivo resultante está ignorado por Git.

## Validación y ejecución local

Backend:

```powershell
$env:GCP_PROJECT_ID = "<project-id>"
$env:GCP_LOCATION = "<region>"
$env:GCP_TABLE_ID = "<project.dataset.table>"
$env:COPILOT_ALLOWED_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
$env:PORT = "8020"
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 0.0.0.0 --port $env:PORT
```

Frontend:

```powershell
Copy-Item frontend/.env.example frontend/.env.local
Set-Location frontend
npm install
npm run dev
```

Pruebas:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
Set-Location frontend
npm test
npm run test:integration
npm run build
```

## Construcción del frontend y canal Firebase beta

Preparar el build de mismo origen:

```powershell
Copy-Item frontend/.env.production.example frontend/.env.production
Set-Location frontend
npm ci
npm run build
Set-Location ..
```

`firebase.beta.json` publica `frontend/dist`, procesa primero `/api/**` y después aplica el fallback de la SPA. Está aislado deliberadamente del nombre predeterminado `firebase.json`: así un despliegue genérico no puede llevar por accidente el rewrite beta al canal `live`. No se incluye `.firebaserc`.

Desplegar o renovar exclusivamente el canal preview:

```powershell
$ProjectId = "fluted-oath-477301-c1"
npx --yes firebase-tools@15.24.0 hosting:channel:deploy react-beta `
  --project $ProjectId `
  --expires 7d `
  --config firebase.beta.json
```

No ejecutar un despliegue Hosting sin `hosting:channel:deploy react-beta` y `--config firebase.beta.json`. La configuración de `live` deberá crearse y revisarse en una etapa productiva separada.

## Construcción de la API

```powershell
$ProjectId = "<project-id>"
$Region = "<region>"
$Repository = "<artifact-registry-repository>"
$Image = "$Region-docker.pkg.dev/$ProjectId/$Repository/inflacion-copilot-api-beta:$(git rev-parse --short HEAD)"

docker build --file Dockerfile.api --tag $Image .
docker run --rm --publish 8080:8080 --env-file .env $Image
Invoke-RestMethod http://127.0.0.1:8080/health
```

El Dockerfile copia únicamente los módulos Python requeridos y no incluye frontend, pruebas, documentación ni el Dockerfile de Streamlit. Streamlit sigue siendo una dependencia transitoria porque `inflacion_service.py` conserva decoradores de caché; el contenedor nunca arranca el servidor Streamlit.

## Cloud Run: comando de referencia

```powershell
$ProjectId = "<project-id>"
$Region = "<region>"
$Repository = "<artifact-registry-repository>"
$RuntimeServiceAccount = "<runtime-service-account>"
$MaxInstances = 2
$Image = "$Region-docker.pkg.dev/$ProjectId/$Repository/inflacion-copilot-api-beta:<image-tag>"

gcloud run deploy inflacion-copilot-api-beta `
  --image $Image `
  --region $Region `
  --service-account $RuntimeServiceAccount `
  --port 8080 `
  --cpu 1 `
  --memory 1Gi `
  --cpu-throttling `
  --min 0 `
  --max $MaxInstances `
  --env-vars-file deployment/cloud-run.env.yaml `
  --no-allow-unauthenticated
```

`--cpu-throttling` mantiene facturación basada en solicitudes; `--min 0` permite escalar a cero. El comando deja el servicio privado. Para la beta ya se aprobó invocación pública exclusivamente sobre el servicio nuevo; el binding reproducible es:

```powershell
gcloud run services add-iam-policy-binding inflacion-copilot-api-beta `
  --region $Region `
  --member allUsers `
  --role roles/run.invoker
```

La cuenta beta tiene `roles/aiplatform.user`, `roles/bigquery.jobUser` y `roles/bigquery.dataViewer` limitado a la tabla de INPC. No reutiliza la cuenta predeterminada con privilegios amplios.

## Rollback y convivencia con Streamlit

- Desplegar la API con el nombre independiente `inflacion-copilot-api-beta`.
- No modificar el servicio existente `inflacion-copilot` ni su Dockerfile.
- Mantener accesible la URL de Streamlit durante la observación paralela.
- Si React presenta una regresión, retirar o revertir Firebase Hosting y dirigir a los usuarios a la URL de Streamlit; no es necesario cambiar datos ni la API determinística.

## Verificar escalado a cero y ausencia de conexiones persistentes

1. Revisar `gcloud run services describe inflacion-copilot-api-beta --region $Region --format yaml`.
2. Confirmar mínimo de instancias `0` y que `run.googleapis.com/cpu-throttling` no sea `false`.
3. Abrir React y dejar la pestaña sin interacción después de cargar el rango.
4. En DevTools, confirmar que no existen conexiones WebSocket o EventSource y que no aparecen solicitudes periódicas.
5. En métricas de Cloud Run, confirmar que el conteo de solicitudes deja de crecer y que las instancias activas regresan a cero después del periodo de inactividad.
6. Comparar CPU facturada antes y después del corte, sin generar tráfico sintético permanente.

Una pestaña React abierta conserva sólo archivos estáticos en el navegador; no debe mantener una solicitud HTTP abierta al backend después de completar `GET /api/copilot/date-range` o una consulta iniciada por el usuario.

La validación beta observó cero solicitudes nuevas durante la ventana sin interacción y, posteriormente, `active=0` e `idle=0` en `run.googleapis.com/container/instance_count`.

## Limitaciones actuales

- Streamlit sigue instalado transitoriamente en la imagen API porque `inflacion_service.py` conserva decoradores de caché; el contenedor no inicia el servidor Streamlit.
- La API beta es pública y todavía no incorpora autenticación ni rate limiting.
- La API de Cloud Billing Budgets no está habilitada; no se activó para esta migración.
- Los contratos TypeScript se validan por compilación y pruebas, no mediante un esquema de runtime en el navegador.
- El canal preview expira y no sustituye un despliegue productivo revisado.

## Pasos posteriores al merge

1. Mantener Streamlit disponible y no redirigir su tráfico.
2. Mantener `react-beta` como canal de observación; no promoverlo a `live` automáticamente.
3. Definir en un cambio separado el servicio, dominio, CORS y archivo Firebase productivos.
4. Repetir pruebas E2E, seguridad, presupuesto y escalado a cero con la configuración productiva propuesta.
5. Solicitar aprobación explícita antes de publicar Firebase `live` o cambiar tráfico.
6. Retirar Streamlit sólo después del periodo de convivencia y con un rollback probado.
