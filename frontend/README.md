# Desarrollo local del frontend

## Backend

Desde la raíz del repositorio:

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.main:app --reload --port 8020
```

También puede usarse el comando equivalente cuando `uvicorn` está disponible en el entorno activo:

```text
uvicorn api.main:app --reload --port 8020
```

## Frontend

Copia `.env.example` como `.env.local`. El valor esperado es:

```env
VITE_API_BASE_URL=http://127.0.0.1:8020
```

Después inicia Vite:

```powershell
cd frontend
npm install
npm run dev
```

La aplicación queda disponible normalmente en `http://localhost:5173`.

## Validación

Las pruebas unitarias del frontend no realizan llamadas externas:

```powershell
npm test
```

La prueba de integración inicia un FastAPI temporal y realiza HTTP real entre el cliente React y la aplicación. Sólo sustituye las fronteras de BigQuery y Vertex AI para impedir accesos reales a GCP:

```powershell
npm run test:integration
```
