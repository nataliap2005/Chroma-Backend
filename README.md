# Chroma-Backend

API en Python (FastAPI) con los cálculos de Chroma: test de colorimetría, catálogo, traductor de tonos y asesor por ocasión. La usa la app [Chroma-App](https://github.com/nataliap2005/Chroma-App).

No guarda usuarias ni tiene credenciales de Supabase: las cuentas y los perfiles los maneja la app con Supabase.

## Ejecutar

Requiere Python 3.11 o superior.

**Mac / Linux**

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m uvicorn app:app --host 0.0.0.0 --port 5050 --reload
```

**Windows**

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app:app --host 0.0.0.0 --port 5050 --reload
```

Documentación interactiva: http://localhost:5050/docs

## Endpoints

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/health` | Estado del servidor |
| GET | `/api/questionnaire` | Las 27 preguntas del test |
| POST | `/api/analyze` | Estación, subtono y paleta a partir de las respuestas |
| GET | `/api/products` | Catálogo completo (688 productos) |
| GET | `/api/catalog/search` | Búsqueda con filtros (`q`, `category`, `brand`, `max_price`) y paginación (`offset`, `limit`) |
| GET | `/api/catalog/facets` | Categorías y marcas con su número de productos |
| POST | `/api/products/personalized` | Catálogo con la compatibilidad (0-100) y sus factores según el test, las opiniones y los favoritos que manda la app |
| GET | `/api/translator` | Tonos equivalentes de otras marcas (ΔE00 ≤ 3, mismo subtono) |
| GET | `/api/occasions` | Ocasiones del asesor |
| POST | `/api/advisor` | Look por ocasión dentro de un presupuesto; recibe la cosmetiquera (`owned_ids`) y las opiniones (`feedback`) |
| — | Planes | Con `CHROMA_SUPABASE_URL` y `CHROMA_SUPABASE_PUBLISHABLE_KEY` en `.env`, el traductor y el asesor piden sesión, descuentan la cuota del mes y dejan fuera las marcas de un plan superior. Sin esos valores, los planes quedan desactivados (`/health` lo indica) |
| POST | `/api/panel` | Panel del alfa (KR1, KR2, KR3 y aciertos por grupo) a partir de los datos agregados de Supabase |

## Estructura

```text
app.py                 API y CORS
catalog_routes.py      Rutas /api/catalog
catalog_service.py     Búsqueda y filtros del catálogo
alpha_routes.py        Catálogo personalizado y panel del alfa
plans.py               Planes Free, Plus y Premium (consulta a Supabase con el token de la usuaria)
questionnaire.py       Test de 27 preguntas
colorimetry.py         Modelo de 12 estaciones
recommender.py         Compatibilidad de cada producto con el perfil
hybrid.py              Traductor (ΔE00) y asesor por ocasión
data/productos_mvp.csv Catálogo: 688 productos con color oficial de 7 marcas
data/fuentes_mvp/      Tonos oficiales tal como los publica cada marca
scripts/audit_catalog.py  Revisión de calidad del catálogo (reporte en reports/)
supabase/migrations/   Tablas de Supabase, en orden (ver supabase/migrations/LEEME.md)
tests/                 Pruebas con pytest
```

## Pruebas

```bash
.venv/bin/python -m pytest -q
```

## Conectar desde el celular

1. Arranca con `--host 0.0.0.0`. Con `127.0.0.1` el celular no llega.
2. Permite el puerto 5050 en el firewall (red privada) y usa la misma Wi-Fi en el computador y el celular.
3. Prueba desde el celular: `http://<IP-del-computador>:5050/health` debe responder `{"status":"ok",...}`.
4. CORS acepta localhost e IPs de la red local. Para otros dominios usa `CHROMA_CORS_ORIGINS` en `.env` (ver `.env.example`). En producción pon `CHROMA_ALLOW_LAN=0`.

## Límites

- El catálogo es una copia del MVP en CSV. Los precios y enlaces deben verificarse en la tienda.
- ΔE00 compara colores digitales: no asegura que dos tonos se vean igual en la piel.
