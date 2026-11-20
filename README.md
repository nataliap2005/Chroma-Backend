<div align="center">

# Chroma · API

### El motor de colorimetría, recomendaciones y pagos de Chroma

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-Postgres%20%2B%20RLS-3ECF8E?logo=supabase&logoColor=white)
![Wompi](https://img.shields.io/badge/pagos-Wompi-2C2A29)
![Pruebas](https://img.shields.io/badge/pruebas-33%20pasan-2f6b47)

[Qué hace](#qué-hace) · [Cómo funciona](#cómo-funciona) · [Endpoints](#endpoints) · [Empezar](#empezar) · [Supabase](#supabase) · [Publicar](#publicar) · [Equipo](#equipo)

</div>

---

**Chroma** recomienda maquillaje según la colorimetría de cada persona: identifica su estación (12 estaciones), su subtono y su paleta, y calcula qué tan compatible es cada producto con ella. Este repositorio es la **API** que hace esos cálculos y cobra los planes. La app que la usa está en **[Chroma-App](https://github.com/nataliap2005/Chroma-App)**, donde también está la presentación completa del proyecto.

## Qué hace

| | Módulo | Qué hace |
|---|---|---|
| 🎨 | **Colorimetría** | Convierte las 27 respuestas del test en una estación, un subtono y una paleta |
| 🛍️ | **Catálogo** | 688 productos de 7 marcas con color oficial; búsqueda, filtros y compatibilidad 0–100 con cada perfil |
| ↔️ | **Traductor de tonos** | Tonos equivalentes de otras marcas con ΔE00 ≤ 3 y el mismo subtono |
| ✨ | **Asesor por ocasión** | Un look completo dentro de un presupuesto, reutilizando la cosmetiquera |
| 🔒 | **Planes** | Marcas por plan y cuotas mensuales del traductor y del asesor |
| 💳 | **Pagos** | Checkout firmado de Wompi y activación del plan por 30 días |
| ✉️ | **Correos** | Confirmación de pago con Resend |
| 📊 | **Panel de resultados** | Indicadores KR1, KR2 y KR3 de la prueba con usuarias, con datos agregados |

## Cómo funciona

### Colorimetría de 12 estaciones

Cada respuesta del test suma pistas sobre **cuatro ejes** independientes:

| Eje | Extremos |
|---|---|
| Temperatura | frío ↔ cálido |
| Profundidad | claro ↔ profundo |
| Saturación | suave ↔ brillante |
| Contraste | bajo ↔ alto |

El perfil resultante se compara con prototipos de las 12 estaciones: Primavera clara, cálida y brillante; Verano claro, suave y frío; Otoño suave, cálido y profundo; Invierno frío, profundo y brillante. La confianza depende de la distancia entre las dos estaciones más cercanas y de las respuestas contradictorias. Es una **heurística orientativa**, no un diagnóstico.

### Compatibilidad con cada producto

Puntaje de 0 a 100 que suma seis factores, cada uno con su motivo: profundidad del tono (28), subtono (25), estación (17), tipo de piel (10), acabado (10) y presupuesto (10). Si la usuaria opinó sobre un tono (acertado, parcial o incorrecto), la compatibilidad de ese producto se ajusta para ella.

### Traductor de tonos (ΔE00)

Compara colores con **CIEDE2000**, implementado sin dependencias. Solo propone un tono si es de la misma categoría, tiene el mismo subtono, no tiene alertas de calidad en el dato y su diferencia de color es ΔE00 ≤ 3. Un resultado vacío es válido: Chroma no anuncia como equivalente un tono distinto.

### Planes y pagos

```mermaid
sequenceDiagram
    participant App
    participant API
    participant Wompi
    participant Supabase
    App->>API: POST /api/payments/checkout {plan}
    API->>Supabase: registra el pago (PENDING)
    API-->>App: URL de Wompi firmada
    App->>Wompi: la usuaria paga
    Wompi->>API: evento firmado (webhook)
    API->>Supabase: apply_payment → plan por 30 días
    API-->>App: correo de confirmación (Resend)
    App->>API: GET /api/payments/status?id= (al volver)
    API->>Wompi: estado real de la transacción
```

- Cada pago lleva la **firma de integridad** de Wompi; los eventos solo se aceptan con la firma del secreto de eventos.
- La API comprueba que el monto sea el del plan. Si Wompi repite el aviso, el plan no se suma dos veces.
- Si el aviso no llega (por ejemplo, porque el servidor estaba dormido), al volver a la app se consulta el estado real en Wompi.

## Endpoints

Documentación interactiva en `/docs` con el servidor encendido.

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/health` | Estado del servidor y de cada integración (catálogo, planes, pagos, correos) |
| GET | `/api/questionnaire` | Las 27 preguntas del test |
| POST | `/api/analyze` | Estación, subtono y paleta a partir de las respuestas |
| GET | `/api/products` | Catálogo completo |
| POST | `/api/products/personalized` | Catálogo con compatibilidad según el test, las opiniones y los favoritos |
| GET | `/api/catalog/search` | Búsqueda (`q`, `category`, `brand`, `max_price`) y paginación (`offset`, `limit`) |
| GET | `/api/catalog/facets` | Categorías y marcas con su número de productos |
| GET | `/api/translator` | Tonos equivalentes de otras marcas (5, 10 o 15 según el plan) |
| GET | `/api/occasions` | Ocasiones del asesor |
| POST | `/api/advisor` | Look por ocasión dentro de un presupuesto |
| POST | `/api/panel` | Indicadores del panel de resultados |
| GET | `/api/payments/config` | Precios y si los pagos están activos |
| POST | `/api/payments/checkout` | Crea el pago y devuelve la URL de Wompi (pide sesión) |
| GET | `/api/payments/status?id=` | Estado de una transacción; si está aprobada, activa el plan |
| POST | `/api/payments/wompi/webhook` | Eventos firmados de Wompi |

El traductor y el asesor piden sesión cuando los planes están activos: la app envía el token de Supabase y la API lo usa para leer el plan y descontar la cuota del mes.

## Estructura

```text
app.py                  Aplicación FastAPI, CORS y endpoints principales
questionnaire.py        Test de 27 preguntas y su validación
colorimetry.py          Modelo de 12 estaciones
recommender.py          Compatibilidad de cada producto con el perfil
hybrid.py               Traductor (CIEDE2000) y asesor por ocasión
alpha_routes.py         Catálogo personalizado y panel de resultados
catalog_service.py      Catálogo (Supabase o CSV), búsqueda y filtros
catalog_routes.py       Rutas /api/catalog
plans.py                Planes y cuotas (con el token de la usuaria)
payments.py             Pagos con Wompi
emails.py               Correos con Resend
data/productos_mvp.csv  Catálogo inicial: 688 productos de 7 marcas
data/fuentes_mvp/       Tonos oficiales tal como los publica cada marca
scripts/                Auditoría del catálogo y generación del SQL del catálogo
reports/                Reporte de calidad del catálogo
supabase/migrations/    Tablas, permisos y funciones de Supabase, en orden
tests/                  Pruebas con pytest
render.yaml, Procfile   Publicación en Render
```

## Empezar

Requisitos: **Python 3.11 o superior**.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/python -m uvicorn app:app --host 0.0.0.0 --port 5050 --reload
```

En Windows: `py -3.11 -m venv .venv` y `.venv\Scripts\python.exe` en lugar de `.venv/bin/python`.

Con el `.env` vacío la API funciona sola: lee el catálogo del CSV y deja planes, pagos y correos desactivados. `http://localhost:5050/health` muestra qué está activo.

**Desde el celular, en la misma Wi-Fi:** arranca con `--host 0.0.0.0`, permite el puerto 5050 en el firewall y abre `http://IP_DEL_COMPUTADOR:5050/health`. CORS acepta IPs de red local mientras `CHROMA_ALLOW_LAN=1`.

### Variables de entorno

| Variable | Para qué |
|---|---|
| `CHROMA_CORS_ORIGINS` | URL de la app publicada (separadas por coma si son varias) |
| `CHROMA_ALLOW_LAN` | `1` en desarrollo (acepta IPs locales), `0` en producción |
| `CHROMA_SUPABASE_URL`, `CHROMA_SUPABASE_PUBLISHABLE_KEY` | Planes, cuotas y catálogo desde Supabase |
| `CHROMA_CATALOG_SOURCE` | `csv` para usar el CSV aunque Supabase esté configurado |
| `CHROMA_SUPABASE_SERVICE_ROLE_KEY` | **Secreta.** Solo en el servidor: confirma pagos |
| `WOMPI_PUBLIC_KEY`, `WOMPI_INTEGRITY_SECRET`, `WOMPI_EVENTS_SECRET` | Pagos con Wompi |
| `CHROMA_APP_URL` | Adonde vuelve la usuaria después de pagar |
| `CHROMA_PRICE_PLUS`, `CHROMA_PRICE_PREMIUM` | Precios en COP (por defecto 19.900 y 34.900) |
| `RESEND_API_KEY`, `CHROMA_EMAIL_FROM` | Correo de confirmación de pago |

### Pruebas

```bash
.venv/bin/python -m pytest -q
```

33 pruebas: test y análisis, catálogo y su calidad, planes y cuotas, pagos (firmas, montos, eventos repetidos) y catálogo desde Supabase. Supabase, Wompi y Resend se simulan, así que no hace falta conexión ni llaves.

## Supabase

Las tablas, permisos (RLS) y funciones están en `supabase/migrations/`, en orden. Se ejecutan en **Supabase → SQL Editor**; cada archivo se puede volver a ejecutar sin dañar nada.

| Archivo | Qué crea |
|---|---|
| `001_perfiles_resultados.sql` | Perfiles y resultados del test; perfil automático al registrarse |
| `002_fotos_perfil.sql` | Foto de perfil en un bucket privado |
| `003_favoritos_cosmetiquera_opiniones.sql` | Favoritos, cosmetiquera, opiniones sobre el tono y datos del panel |
| `004_planes_cuotas_admin.sql` | Planes, marcas por plan, cuotas mensuales y funciones de administración |
| `005_catalogo_pagos.sql` | Catálogo administrable, fotos de productos, opiniones para administradoras, pagos y vencimiento del plan |
| `006_catalogo_inicial.sql` | Los 688 productos iniciales (se genera con `python scripts/export_catalog_sql.py`) |
| `007_opiniones_looks.sql` | Opiniones sobre los looks del asesor (le gusta, lo usaría, comentario) |

Más detalle, y cómo nombrar a la primera administradora, en [supabase/migrations/LEEME.md](supabase/migrations/LEEME.md).

## Publicar

La beta corre gratis en **Render** con el dominio propio:

| Parte | Dónde | Dominio |
|---|---|---|
| Esta API | Render, web service gratuito | `api.tu-dominio.com` |
| La app | Render, sitio estático | `app.tu-dominio.com` |
| Datos y cuentas | Supabase, plan gratuito | — |

1. Ejecuta las migraciones en Supabase (sección anterior).
2. Render → **New → Blueprint** → este repositorio. `render.yaml` define el servicio (Python, plan gratuito, chequeo de salud en `/health`) y pide las variables de entorno.
3. **Settings → Custom Domains** → `api.tu-dominio.com`, con un registro `CNAME` hacia la URL `.onrender.com` del servicio.
4. En Wompi → Desarrolladores → URL de eventos: `https://api.tu-dominio.com/api/payments/wompi/webhook`.
5. Para los correos de registro y contraseña, configura Resend como SMTP en Supabase (Authentication → Emails → SMTP Settings).

`https://api.tu-dominio.com/health` debe decir `catalog: supabase`, `planes: activos`, `pagos: activos` y `correos: activos`.

**Plan gratuito de Render:** el servicio se duerme tras 15 minutos sin visitas y tarda cerca de un minuto en despertar. No guarda archivos en disco, lo que no afecta a Chroma porque todo vive en Supabase. El plan pagado más barato elimina la espera.

## Calidad de los datos

- Colores oficiales publicados por cada marca (`data/fuentes_mvp/`), con nivel de calidad por tono: `ok`, `ambiguo`, `incoherente` o `transparente`.
- `python scripts/audit_catalog.py` revisa ids, colores, precios, imágenes y enlaces, y deja el reporte en `reports/auditoria_catalogo.json`.
- Precios revisados a mano en tiendas de Colombia; pueden cambiar.
- ΔE00 compara colores digitales: no garantiza que dos tonos se vean igual sobre la piel.

## Equipo

Proyecto del curso **Data Thinking** · Universidad Autónoma de Occidente (UAO), Cali · 2026.

| | Integrante | Aportes principales |
|---|---|---|
| 🎨 | **Natalia Paredes** · [GitHub](https://github.com/nataliap2005) | Base del proyecto, motor de colorimetría y app Ionic |
| 🗄️ | **Mariana Cifuentes** | Servidor, base de datos y catálogo de bases |
| 🖌️ | **María Paula Pinillo** | Interfaz, tiendas y fotos de productos |
| 💄 | **Estefanía Hernández** · [GitHub](https://github.com/HEstefaniaR) | Tonos y paletas, planes, pagos, administración y publicación de la beta |

<div align="center">

**Chroma** · Belleza personalizada con datos

</div>
