# Operación productiva

Guía operativa para la experiencia productiva React + FastAPI de Inflación Copilot MX.

> Los comandos marcados como remotos cambian recursos de Google Cloud o Firebase. Antes de ejecutarlos se debe confirmar proyecto, región, cuenta autenticada, commit, imagen, servicio y autorización de cambio. Esta guía no autoriza por sí misma un despliegue.

## Estado productivo

| Componente | Estado |
|---|---|
| Firebase Hosting live | Frontend React productivo |
| Configuración Hosting | `firebase.production.json` |
| Servicio FastAPI | `inflacion-copilot-api` |
| Región | `us-central1` |
| Contenedor | `Dockerfile.api` |
| API beta | `inflacion-copilot-api-beta`, separada de producción |
| Streamlit | `inflacion-copilot`, rollback temporal |
| Workflow Streamlit | `.github/workflows/deploy.yml`, sólo `workflow_dispatch` |

URL pública del frontend:

```text
https://fluted-oath-477301-c1.web.app
```

## Arquitectura

```text
Usuario
  → Firebase Hosting live
  → frontend/dist
  → React + TypeScript + Vite
  → /api/copilot/**
  → rewrite /api/**
  → Cloud Run: inflacion-copilot-api
  → BigQuery / INPC
  → Vertex AI / Gemini

Sistemas consumidores
  → Cloud Run: inflacion-copilot-api
  → /inflation/**
  → BigQuery / INPC

Rollback temporal
  → Cloud Run: inflacion-copilot
  → Streamlit
```

`firebase.production.json` debe apuntar únicamente a `inflacion-copilot-api`. `firebase.beta.json` debe apuntar únicamente a `inflacion-copilot-api-beta`.

## Variables

### Backend

| Variable | Uso |
|---|---|
| `GCP_PROJECT_ID` | Proyecto de ejecución y facturación |
| `GCP_LOCATION` | Región de Vertex AI |
| `GCP_TABLE_ID` | Tabla completa del INPC |
| `COPILOT_ALLOWED_ORIGINS` | Orígenes permitidos separados por coma; no acepta `*` |
| `PORT` | Inyectada por Cloud Run |

La configuración desplegable se deriva de `deployment/cloud-run.env.example.yaml`. La copia `deployment/cloud-run.env.yaml` está ignorada por Git y no debe contenerse en commits.

### Frontend

```env
VITE_API_BASE_URL=/api
```

La variable se resuelve durante el build. No debe incluirse una URL beta en un build productivo.

## Validación previa

Desde un árbol limpio y el commit autorizado:

```powershell
.\.venv\Scripts\python.exe -m pytest -q

cd frontend
npm ci
npm test
npm run test:integration
npm run build
cd ..
```

Validar además:

```powershell
Get-Content -Raw firebase.production.json | ConvertFrom-Json
git status --short
git rev-parse HEAD
```

Antes de cualquier operación remota se debe comprobar:

- todas las pruebas pasan;
- el build usa `VITE_API_BASE_URL=/api`;
- no hay referencias a `inflacion-copilot-api-beta` en `firebase.production.json`;
- la imagen usa un tag inmutable;
- Streamlit está saludable y disponible;
- existe una revisión FastAPI anterior para rollback;
- no se requieren cambios de IAM fuera del servicio productivo.

## Build de la API

Build local:

```powershell
$ProjectId = "<project-id>"
$Region = "us-central1"
$Repository = "<artifact-registry-repository>"
$Sha = git rev-parse HEAD
$Image = "$Region-docker.pkg.dev/$ProjectId/$Repository/inflacion-copilot-api:$Sha"

docker build --file Dockerfile.api --tag $Image .
docker run --rm --publish 8080:8080 --env-file .env $Image
Invoke-RestMethod http://127.0.0.1:8080/health
```

El proceso del contenedor es Uvicorn con `api.main:app`. `Dockerfile.api` no inicia Streamlit.

Publicación de imagen remota:

```powershell
# Operación remota: requiere autorización.
docker push $Image
```

No se recomienda utilizar tags mutables para imágenes productivas.

## Despliegue controlado de FastAPI

El servicio productivo ya existe. No se debe crear otro servicio con un nombre parecido.

```powershell
# Operación remota: revisar todos los valores antes de ejecutar.
$RuntimeServiceAccount = "<production-runtime-service-account>"
$MaxInstances = 2
$ShortSha = (git rev-parse --short HEAD)

gcloud run deploy inflacion-copilot-api `
  --image $Image `
  --region $Region `
  --service-account $RuntimeServiceAccount `
  --port 8080 `
  --cpu 1 `
  --memory 1Gi `
  --cpu-throttling `
  --min 0 `
  --max $MaxInstances `
  --concurrency 20 `
  --timeout 120 `
  --env-vars-file deployment/cloud-run.env.yaml `
  --tag "candidate-$ShortSha" `
  --no-traffic
```

Después de crear la revisión sin tráfico:

1. obtener el nombre y URL etiquetada de la revisión;
2. validar `/health`;
3. validar `/copilot/date-range`, `/copilot/history` y `/copilot/query`;
4. validar rechazos y errores controlados;
5. validar `/inflation/period`, `/inflation/average-period` y `/inflation/monthly-comparable`;
6. confirmar cuenta de servicio, CPU throttling, mínimo 0 y máximo explícito;
7. sólo entonces promover el tráfico con una autorización separada.

Ejemplo de promoción deliberada:

```powershell
# Operación remota: cambia el tráfico productivo.
$Revision = "<validated-revision-name>"
gcloud run services update-traffic inflacion-copilot-api `
  --region $Region `
  --to-revisions "$Revision=100"
```

No se deben eliminar revisiones anteriores durante el despliegue.

## Build y publicación de Firebase live

Generar nuevamente el frontend:

```powershell
cd frontend
$env:VITE_API_BASE_URL="/api"
npm ci
npm test
npm run test:integration
npm run build
cd ..
```

Revisar el artefacto:

- contiene `/api`;
- no contiene el nombre del servicio beta;
- no contiene URLs Cloud Run codificadas;
- `frontend/dist` continúa ignorado por Git.

Publicación exclusiva de Hosting:

```powershell
# Operación remota: publica Firebase live.
$ProjectId = "fluted-oath-477301-c1"
npx --yes firebase-tools@15.24.0 deploy `
  --only hosting `
  --project $ProjectId `
  --config firebase.production.json `
  --non-interactive
```

No ejecutar este comando con `firebase.beta.json`. No agregar otros productos Firebase al parámetro `--only`.

## Smoke test posterior

En la URL live:

1. confirmar la carga del rango dinámico;
2. ejecutar una consulta válida;
3. revisar monto, inflación, INPC inicial/final y resumen;
4. revisar gráfica SVG, tabla y comentario analítico;
5. probar pregunta fuera de dominio;
6. probar fecha fuera de rango;
7. recargar directamente la SPA;
8. validar viewport móvil y navegación por teclado;
9. comprobar que la consola no contiene errores;
10. comprobar que Network no contiene WebSocket, EventSource ni solicitudes periódicas.

En el backend:

```powershell
$ApiUrl = "<production-api-url>"
Invoke-RestMethod "$ApiUrl/health"
Invoke-RestMethod "$ApiUrl/copilot/date-range"
```

Las consultas reales a Gemini y BigQuery deben ser pocas, explícitas y controladas.

## Escalado a cero

Configuración requerida:

- CPU throttling habilitado;
- mínimo de instancias igual a 0;
- máximo conservador y explícito;
- ausencia de WebSocket, EventSource y polling.

Prueba:

1. ejecutar una consulta desde React live;
2. registrar la hora de finalización;
3. dejar la pestaña abierta sin interacción;
4. confirmar que el conteo de solicitudes no aumenta;
5. observar `active=0`;
6. observar posteriormente `idle=0` si Cloud Monitoring publica el dato dentro de la ventana;
7. cerrar la pestaña al terminar.

No se deben inventar métricas si Monitoring no entrega puntos suficientes.

## Rollback

### Frontend

Firebase conserva versiones anteriores. Ante una regresión:

1. detener cualquier promoción adicional;
2. identificar la última versión live saludable;
3. obtener aprobación para restaurarla mediante Firebase Console o una operación CLI explícita;
4. repetir el smoke test.

No reutilizar el canal beta como sustituto silencioso de live.

### FastAPI

Cloud Run conserva revisiones anteriores. Ante una regresión:

1. mantener la revisión fallida disponible para diagnóstico;
2. identificar la última revisión saludable;
3. obtener aprobación para reasignar el tráfico;
4. validar contratos conversacionales y determinísticos.

No eliminar imágenes ni revisiones como parte del rollback.

### Streamlit

El servicio `inflacion-copilot` permanece disponible como respaldo temporal. Su despliegue sólo se ejecuta manualmente mediante `workflow_dispatch`.

Usar Streamlit como rollback no requiere modificar BigQuery ni retirar FastAPI. No se debe ejecutar su workflow para una simple validación ni cambiar su tráfico durante un despliegue normal de React.

## Seguridad operativa

- No subir `.env`, `deployment/cloud-run.env.yaml`, claves JSON ni tokens.
- Mantener BigQuery y Vertex AI privados.
- Limitar `allUsers`, cuando sea necesario, a `roles/run.invoker` del servicio HTTP.
- Usar una cuenta de servicio dedicada con permisos mínimos.
- Revisar proyecto y región en cada comando.
- No ejecutar despliegues desde un árbol sucio.
- No desplegar frontend y backend simultáneamente sin una secuencia y rollback definidos.
- No retirar Streamlit hasta una decisión operativa posterior.

## Limitaciones vigentes

- Streamlit permanece instalado como dependencia transitoria de la imagen API por los decoradores de caché reutilizados, aunque no se inicia como servidor.
- La API pública no tiene autenticación ni rate limiting.
- TypeScript no valida en runtime el JSON recibido.
- Google Fonts depende de conectividad externa.
- El pipeline de carga INEGI no se administra desde este repositorio.

## Registro mínimo de un cambio productivo

Conservar en el PR o ticket:

- commit;
- imagen y digest;
- revisión Cloud Run;
- versión Firebase;
- cuenta de servicio;
- configuración de escalado;
- pruebas ejecutadas;
- resultado del smoke test;
- resultado de escalado a cero;
- estado de Streamlit y beta;
- recursos modificados;
- confirmación de que no se eliminó ningún recurso.
