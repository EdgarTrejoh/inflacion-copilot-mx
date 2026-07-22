# Preparación de despliegue paralelo

Esta guía contiene comandos de referencia. Ninguno debe ejecutarse hasta seleccionar el proyecto, la región, la cuenta de servicio, el dominio y la política de acceso.

## Arquitectura objetivo

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

## Construcción del frontend y Firebase

Preparar el build de mismo origen:

```powershell
Copy-Item frontend/.env.production.example frontend/.env.production
Set-Location frontend
npm ci
npm run build
Set-Location ..
```

`firebase.json` publica `frontend/dist`, procesa primero `/api/**` y después aplica el fallback de la SPA. La región del rewrite está preparada con la región ya usada por el proyecto (`us-central1`); debe cambiarse junto con `$Region` si se elige otra. No se incluye `.firebaserc` para evitar asociar accidentalmente un proyecto remoto.

Comandos futuros, no ejecutados en esta etapa:

```powershell
firebase use --add
firebase deploy --only hosting
```

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
$MaxInstances = 3
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

`--cpu-throttling` mantiene facturación basada en solicitudes; `--min 0` permite escalar a cero. El comando deja el servicio privado. Firebase Hosting no podrá invocarlo hasta que se tome una decisión explícita de acceso. Si se aprueba acceso público, el cambio IAM separado sería:

```powershell
gcloud run services add-iam-policy-binding inflacion-copilot-api-beta `
  --region $Region `
  --member allUsers `
  --role roles/run.invoker
```

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
