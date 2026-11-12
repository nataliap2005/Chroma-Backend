"""Chroma: API de cálculo sin autenticación propia ni persistencia de usuarios.

Supabase Auth + PostgreSQL son manejados desde Ionic. Esta API no acepta escritura
privilegiada en Supabase ni distribuye claves privadas. Datos de productos son una
instantánea del MVP original para pruebas; pueden sustituirse cuando el equipo
consolide el catálogo.
"""
import csv
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

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

app = FastAPI(title='Chroma Engine API', version='0.1.0')

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

# CHROMA_CORS_ORIGINS AÑADE orígenes a la lista por defecto (antes la reemplazaba).
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


def products() -> list[dict[str, Any]]:
    path = ROOT / 'data' / 'productos_mvp.csv'
    with path.open(encoding='utf-8-sig', newline='') as f:
        rows = [dict(x) for x in csv.DictReader(f)]
    for p in rows:
        p['precio_cop'] = int(p['precio_cop'])
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
    return {'status': 'ok', 'engine': 'python', 'catalog': 'snapshot-mvp'}


@app.get('/api/questionnaire')
def questionnaire():
    return {'version': QUESTIONNAIRE_VERSION, 'questions': QUESTIONS}


@app.post('/api/analyze')
def analyze_answers(payload: AnswersPayload):
    answers, analysis = get_analysis(payload.answers)
    return {'ok': True, 'answers': answers, 'analysis': analysis, 'profile': {'answers': answers, 'analysis': analysis, 'season': analysis['season'], 'undertone': analysis['undertone']}}


@app.get('/api/products')
def list_products():
    return {'products': products(), 'catalog_status': 'mvp_snapshot'}


@app.get('/api/translator')
def translator(product_id: str, limit: int = Query(5, ge=1, le=20), max_price: int | None = Query(None, ge=0), cheaper: bool = False):
    try:
        return translate_shades(products(), product_id, limit=limit, max_price=max_price, only_cheaper=cheaper)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get('/api/occasions')
def occasions():
    return {'occasions': {key: {'name': val['name'], 'description': val['description']} for key, val in OCCASIONS.items()}}


@app.post('/api/advisor')
def advisor(payload: AdvisorPayload):
    if payload.occasion not in OCCASIONS:
        raise HTTPException(status_code=422, detail='Ocasión inválida')
    answers, analysis = get_analysis(payload.answers)
    profile = {'answers': answers, 'analysis': analysis, 'season': analysis['season'], 'undertone': analysis['undertone']}
    try:
        catalog = [shape_product(p, profile) for p in products()]
        result = recommend_look(catalog, payload.owned_ids, profile, payload.occasion, payload.budget)
        result['catalog_status'] = 'mvp_snapshot'
        return result
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc