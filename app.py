"""Chroma: API de cálculo. Cuentas y datos de cada usuaria viven en Supabase (los maneja la app).

El catálogo se lee de Supabase (o del CSV del MVP si no está configurado, ver catalog_service.py).
La única escritura privilegiada en Supabase es la de los pagos de Wompi (payments.py), con la
clave service_role que solo existe en el servidor.
"""
import logging
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from catalog_routes import router as catalog_router
from alpha_routes import router as alpha_router, ToneOpinion
from catalog_service import catalog_status, configured_source, get_products
import emails
import payments
import plans

from questionnaire import QUESTIONS, QUESTIONNAIRE_VERSION, validate_questionnaire
from colorimetry import analyze
from recommender import shape_product
from hybrid import OCCASIONS, translate_shades, recommend_look

ROOT = Path(__file__).resolve().parent

try:  # uvicorn NO lee .env por sí solo; se carga aquí
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env')
except ImportError:
    pass

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')

app = FastAPI(title='Chroma Engine API', version='0.2.0-beta')
app.include_router(catalog_router)
app.include_router(alpha_router)
app.include_router(payments.router)

# --- CORS -------------------------------------------------------------------
# Orígenes exactos permitidos (web, ionic serve, Capacitor iOS/Android).
# En Android, Capacitor sirve la app desde https://localhost (androidScheme por defecto).
default_origins = [
    "http://localhost:8100",
    "http://127.0.0.1:8100",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost",
    "https://localhost",
    "capacitor://localhost",
    "ionic://localhost",
]

# CHROMA_CORS_ORIGINS suma orígenes a la lista por defecto.
env_origins = [x.strip() for x in os.environ.get('CHROMA_CORS_ORIGINS', '').split(',') if x.strip()]
origins = list(dict.fromkeys(default_origins + env_origins))

# Desarrollo desde el celular: la web se abre como http://<IP-del-PC>:5173, así que el
# origen cambia con la IP. Se aceptan IPs de red local (192.168.x.x, 10.x.x.x, 172.16-31.x.x)
# y localhost en cualquier puerto. Desactívalo en producción con CHROMA_ALLOW_LAN=0.
LAN_REGEX = (
    r"^https?://(localhost|127\.0\.0\.1"
    r"|192\.168\.\d{1,3}\.\d{1,3}"
    r"|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})(:\d+)?$"
)
allow_lan = os.environ.get('CHROMA_ALLOW_LAN', '1') != '0'

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=LAN_REGEX if allow_lan else None,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

class AnswersPayload(BaseModel):
    answers: dict[str, Any]

class AdvisorPayload(BaseModel):
    occasion: str
    budget: int = Field(ge=0, le=50_000_000)
    answers: dict[str, Any]
    owned_ids: list[str] = Field(default_factory=list, max_length=1000)
    # Opiniones de la usuaria sobre cada tono: ajustan la compatibilidad
    feedback: dict[str, ToneOpinion] = Field(default_factory=dict, max_length=2000)


# Tonos alternativos que muestra el traductor por consulta, según el plan (hoja 05 PLANES)
ALTERNATIVAS = {'free': 5, 'plus': 10, 'premium': 15}


def products() -> list[dict[str, Any]]:
    rows = get_products()
    for p in rows:
        p['panes'] = p.get('panes') or ''
    return rows


def get_analysis(raw: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        validated = validate_questionnaire(raw)
        result = analyze(validated)
        return validated, result
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get('/health')
def health():
    return {'status': 'ok', 'engine': 'python', 'version': app.version,
            'catalog': 'supabase' if configured_source() == 'supabase' else 'csv-mvp',
            'planes': 'activos' if plans.gateway() else 'desactivados (falta CHROMA_SUPABASE_URL)',
            'pagos': 'activos' if payments.configured() else 'desactivados (faltan las llaves de Wompi)',
            'correos': 'activos' if emails.configured() else 'desactivados (falta RESEND_API_KEY)'}


@app.get('/api/questionnaire')
def questionnaire():
    return {'version': QUESTIONNAIRE_VERSION, 'questions': QUESTIONS}


@app.post('/api/analyze')
def analyze_answers(payload: AnswersPayload):
    answers, analysis = get_analysis(payload.answers)
    return {'ok': True, 'answers': answers, 'analysis': analysis, 'profile': {'answers': answers, 'analysis': analysis, 'season': analysis['season'], 'undertone': analysis['undertone']}}


@app.get('/api/products')
def list_products():
    return {'products': products(), 'catalog_status': catalog_status()}


@app.get('/api/translator')
def translator(product_id: str, limit: int = Query(5, ge=1, le=20), max_price: int | None = Query(None, ge=0), cheaper: bool = False,
               authorization: str | None = Header(None)):
    gw, token = plans.gateway(), plans.token_from(authorization)
    plan = None
    if gw:
        if not token:
            raise HTTPException(401, 'Inicia sesión en la pestaña Cuenta para usar el traductor.')
        plan = gw.my_plan(token)
    # Solo se comparan marcas del plan de la usuaria (el tono de referencia siempre entra)
    rows = [p for p in products() if plans.accesible(p, plan) or p['id'] == product_id]
    if plan is not None:
        limit = min(limit, ALTERNATIVAS.get(plan.get('plan', 'free'), 5))
    try:
        result = translate_shades(rows, product_id, limit=limit, max_price=max_price, only_cheaper=cheaper)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if gw:
        result['plan'] = gw.consume(token, 'traductor')
    return result


@app.get('/api/occasions')
def occasions():
    return {'occasions': {key: {'name': val['name'], 'description': val['description']} for key, val in OCCASIONS.items()}}


@app.post('/api/advisor')
def advisor(payload: AdvisorPayload, authorization: str | None = Header(None)):
    if payload.occasion not in OCCASIONS:
        raise HTTPException(status_code=422, detail='Ocasión inválida')
    gw, token = plans.gateway(), plans.token_from(authorization)
    plan = None
    if gw:
        if not token:
            raise HTTPException(401, 'Inicia sesión en la pestaña Cuenta para usar el asesor.')
        plan = gw.my_plan(token)
    answers, analysis = get_analysis(payload.answers)
    profile = {'answers': answers, 'analysis': analysis, 'season': analysis['season'], 'undertone': analysis['undertone']}
    try:
        catalog = [shape_product(p, profile, payload.feedback[p['id']].model_dump() if p['id'] in payload.feedback else None)
                   for p in products()]
        # Marcas de un plan superior solo entran si ya están en la cosmetiquera
        owned = set(payload.owned_ids)
        catalog = [p for p in catalog if plans.accesible(p, plan) or p['id'] in owned]
        result = recommend_look(catalog, payload.owned_ids, profile, payload.occasion, payload.budget)
        result['catalog_status'] = catalog_status()
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if gw:
        result['plan'] = gw.consume(token, 'looks')
    return result