# Chroma-Backend

API de cálculo para Chroma. **Proyecto independiente** de Ionic y Supabase.

Ejecutar en Windows, dentro de esta carpeta:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app:app --host 0.0.0.0 --port 5050 --reload
```

Endpoints: `/health`, `/docs`, `GET /api/questionnaire`, `POST /api/analyze`, `GET /api/products`, `GET /api/translator`, `GET /api/occasions`, `POST /api/advisor`.

El catálogo CSV es una copia de prueba del MVP; no sustituye PostgreSQL de Supabase. No hay credenciales Supabase en el backend. Para pruebas ejecuta `.venv\Scripts\python.exe -m pytest -q`.


## Conectar desde el celular
1. Arranca con `--host 0.0.0.0` (con `127.0.0.1` el celular nunca llega).
2. Permite el puerto 5050 en el Firewall de Windows (red privada) y usa la misma Wi-Fi en PC y celular.
3. Prueba desde el celular: `http://<IP-del-PC>:5050/health` debe responder `{"status":"ok",...}`.
4. CORS ya acepta localhost y IPs de red local; para dominios extra usa `CHROMA_CORS_ORIGINS` en `.env`.
