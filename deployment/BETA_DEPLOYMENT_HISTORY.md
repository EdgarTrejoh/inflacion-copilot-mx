# Historial del despliegue beta

> **Documento histórico.** Describe la arquitectura beta utilizada para validar la migración. No representa la arquitectura productiva actual ni autoriza despliegues. Para operación vigente consulta [PRODUCTION_OPERATIONS.md](PRODUCTION_OPERATIONS.md).

## Propósito de la beta

La beta permitió comprobar en paralelo que:

- React podía sustituir la experiencia funcional de Streamlit;
- FastAPI podía exponer contratos conversacionales sin mezclar la API determinística;
- Firebase Hosting podía usar un mismo origen mediante `/api/**`;
- una pestaña estática abierta no mantenía sesiones o solicitudes persistentes;
- Cloud Run podía volver a cero instancias;
- Streamlit podía permanecer intacto como rollback.

## Arquitectura beta histórica

```text
Usuario
  → canal preview de Firebase Hosting: react-beta
  → React + TypeScript + Vite
  → rewrite /api/**
  → Cloud Run: inflacion-copilot-api-beta
  → BigQuery / INPC
  → Vertex AI / Gemini

Rollback independiente:
  Cloud Run: inflacion-copilot (Streamlit)
```

Recursos que identificaron esa etapa:

- configuración: `firebase.beta.json`;
- canal preview: `react-beta`;
- backend: `inflacion-copilot-api-beta`;
- región: `us-central1`;
- cuenta de ejecución beta: `inflacion-copilot-api-beta@fluted-oath-477301-c1.iam.gserviceaccount.com`.

La beta permanece separada de `firebase.production.json` y de `inflacion-copilot-api`. No debe presentarse como la experiencia principal.

## Variables utilizadas

Backend:

- `GCP_PROJECT_ID`;
- `GCP_LOCATION`;
- `GCP_TABLE_ID`;
- `COPILOT_ALLOWED_ORIGINS`;
- `PORT`, inyectada por Cloud Run.

Frontend:

- `VITE_API_BASE_URL=/api`.

No se almacenan credenciales en el repositorio. `deployment/cloud-run.env.example.yaml` contiene únicamente marcadores; su copia operativa `deployment/cloud-run.env.yaml` está ignorada por Git.

## Reproducción local de la arquitectura

Estos comandos sólo levantan procesos locales:

```powershell
$env:GCP_PROJECT_ID = "<project-id>"
$env:GCP_LOCATION = "<region>"
$env:GCP_TABLE_ID = "<project.dataset.table>"
$env:COPILOT_ALLOWED_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 0.0.0.0 --port 8020
```

En otra terminal:

```powershell
cd frontend
Copy-Item .env.example .env.local
npm ci
npm run dev
```

## Reproducción del canal beta

> Los siguientes comandos modifican recursos remotos. Son una referencia histórica y sólo deben ejecutarse con autorización explícita, proyecto y cuenta verificados.

Build con mismo origen:

```powershell
cd frontend
$env:VITE_API_BASE_URL="/api"
npm ci
npm run build
cd ..
```

Publicación exclusiva del canal preview:

```powershell
$ProjectId = "fluted-oath-477301-c1"
npx --yes firebase-tools@15.24.0 hosting:channel:deploy react-beta `
  --project $ProjectId `
  --expires 7d `
  --config firebase.beta.json
```

No debe utilizarse `firebase.beta.json` para Firebase live.

## Imagen y servicio beta

La imagen se identifica con un SHA inmutable:

```powershell
$ProjectId = "<project-id>"
$Region = "<region>"
$Repository = "<artifact-registry-repository>"
$Sha = git rev-parse HEAD
$Image = "$Region-docker.pkg.dev/$ProjectId/$Repository/inflacion-copilot-api-beta:$Sha"

docker build --file Dockerfile.api --tag $Image .
```

Referencia histórica de despliegue:

```powershell
$RuntimeServiceAccount = "<beta-runtime-service-account>"
$MaxInstances = 2

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

La exposición pública, si se reproduce, debe limitarse a `roles/run.invoker` sobre el servicio beta. No deben hacerse públicos BigQuery, Vertex AI ni la cuenta de servicio.

## Resultado histórico

La validación beta comprobó que:

- los endpoints conversacionales funcionaban con datos reales controlados;
- los endpoints determinísticos permanecían independientes;
- no existían WebSocket, EventSource ni polling;
- durante la inactividad no aparecían solicitudes nuevas;
- Cloud Run alcanzaba `active=0` y posteriormente `idle=0`;
- Streamlit conservaba imagen, tráfico e IAM.

## Relación con producción

La beta sirvió como evidencia antes del corte productivo. La producción actual utiliza:

- Firebase live con `firebase.production.json`;
- `inflacion-copilot-api`;
- una cuenta de servicio productiva separada;
- Streamlit únicamente como rollback temporal.

No se debe promover automáticamente el canal beta ni reutilizar sus nombres en producción.
