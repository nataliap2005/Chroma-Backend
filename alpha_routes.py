"""Catálogo personalizado (compatibilidad) y panel de resultados de la prueba con usuarias.

La API no guarda datos de usuarias. Favoritos, cosmetiquera y opiniones viven en
Supabase; la app los envía en cada consulta y esta API solo calcula.
"""
from typing import Any, Literal

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

import plans
from catalog_service import get_products
from colorimetry import analyze
from questionnaire import validate_questionnaire
from recommender import shape_product

router = APIRouter(tags=['resultados'])

RESULTADOS_TONO = ('acertado', 'parcial', 'incorrecto')
MOTIVOS_TONO = {'muy_claro': 'Muy claro', 'muy_oscuro': 'Muy oscuro', 'muy_rosado': 'Muy rosado (frío)',
                'muy_amarillo': 'Muy amarillo (cálido)', 'acabado': 'El acabado', 'otro': 'Otro'}


class ToneOpinion(BaseModel):
    tono_resultado: Literal['acertado', 'parcial', 'incorrecto']


class PersonalizedPayload(BaseModel):
    answers: dict[str, Any] | None = None
    feedback: dict[str, ToneOpinion] = Field(default_factory=dict, max_length=2000)
    favorites: list[str] = Field(default_factory=list, max_length=2000)
    ids: list[str] | None = Field(default=None, max_length=2000)


def build_profile(answers: dict[str, Any] | None) -> dict[str, Any] | None:
    """Perfil a partir de las respuestas del test; None si no hay test."""
    if not answers:
        return None
    try:
        validated = validate_questionnaire(answers)
        analysis = analyze(validated)
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {'answers': validated, 'analysis': analysis, 'season': analysis['season'], 'undertone': analysis['undertone']}


def personalize(products: list[dict[str, Any]], profile: dict[str, Any] | None,
                feedback: dict[str, ToneOpinion], favorites: set[str]) -> list[dict[str, Any]]:
    out = []
    for p in products:
        opinion = feedback.get(p['id'])
        out.append(shape_product(p, profile, opinion.model_dump() if opinion else None, p['id'] in favorites))
    return out


@router.post('/api/products/personalized')
def personalized(payload: PersonalizedPayload, authorization: str | None = Header(None)):
    """Catálogo con la compatibilidad (0-100), sus factores y el candado de los planes."""
    gw = plans.gateway()
    plan = gw.my_plan(plans.token_from(authorization)) if gw else None
    profile = build_profile(payload.answers)
    catalog = get_products()
    if payload.ids is not None:
        wanted = set(payload.ids)
        catalog = [p for p in catalog if p['id'] in wanted]
    shaped = personalize(catalog, profile, payload.feedback, set(payload.favorites))
    plans.mark(shaped, plan)
    return {'products': shaped, 'personalized': profile is not None, 'plan': plan, 'catalog_status': 'mvp_snapshot'}


# --------------------------------------------------------------------------- panel de resultados

class PanelOpinion(BaseModel):
    product_id: str
    tono_resultado: Literal['acertado', 'parcial', 'incorrecto']
    motivo_tono: str = ''
    forma_evaluacion: str = ''
    confidence_before: int | None = Field(default=None, ge=1, le=5)
    confidence_after: int | None = Field(default=None, ge=1, le=5)
    undertone: str | None = None


class PanelPayload(BaseModel):
    """Lo que entrega la función alpha_panel_data() de Supabase: datos agregados, sin identificar a nadie."""
    usuarias: int = Field(ge=0)
    con_perfil: int = Field(ge=0)
    usuarias_con_feedback: int = Field(ge=0)
    usuarias_activas: int = Field(ge=0)
    evaluaciones: list[PanelOpinion] = Field(default_factory=list, max_length=100_000)


def _dist(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    c = {k: sum(1 for r in rows if r['tono_resultado'] == k) for k in RESULTADOS_TONO}
    return {'n': n, **c,
            'acierto_pct': round((c['acertado'] + c['parcial']) / n * 100) if n else None,
            'acertado_pct': round(c['acertado'] / n * 100) if n else None}


def _count(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    keys = sorted({r[field] for r in rows if r.get(field)})
    return {k: sum(1 for r in rows if r.get(field) == k) for k in keys}


def panel_resultados(data: PanelPayload) -> dict[str, Any]:
    """Indicadores KR1, KR2 y KR3 y aciertos por grupo, calculados sobre los datos agregados de Supabase."""
    catalog = {p['id']: p for p in get_products()}
    rows = []
    for e in data.evaluaciones:
        p = catalog.get(e.product_id)
        if not p:
            continue                       # producto que salió del catálogo
        rows.append({**e.model_dump(), 'categoria': p['categoria'], 'marca': p['marca'], 'nivel': p['nivel'],
                     'nombre': p['nombre'], 'tono': p['tono']})

    def grupos(field: str) -> dict[str, Any]:
        keys = sorted({r[field] for r in rows if r.get(field)})
        return {k: _dist([r for r in rows if r.get(field) == k]) for k in keys}

    pares = [r for r in rows if r['confidence_before'] and r['confidence_after']]
    antes = sum(r['confidence_before'] for r in pares) / len(pares) if pares else None
    despues = sum(r['confidence_after'] for r in pares) / len(pares) if pares else None
    cambio = round((despues - antes) / antes * 100) if antes else None
    fallos: dict[str, dict[str, Any]] = {}
    for r in rows:
        if r['tono_resultado'] == 'incorrecto':
            f = fallos.setdefault(r['product_id'], {'id': r['product_id'], 'marca': r['marca'], 'nombre': r['nombre'],
                                                    'tono': r['tono'], 'n': 0})
            f['n'] += 1
    tono = _dist(rows)
    return {
        'usuarias': data.usuarias, 'con_perfil': data.con_perfil,
        'usuarias_con_feedback': data.usuarias_con_feedback, 'evaluaciones': len(rows),
        'tono': tono,
        'motivos': {MOTIVOS_TONO.get(k, k): v for k, v in
                    _count([r for r in rows if r['tono_resultado'] != 'acertado'], 'motivo_tono').items()},
        'forma': _count(rows, 'forma_evaluacion'),
        'por_categoria': grupos('categoria'), 'por_marca': grupos('marca'), 'por_nivel': grupos('nivel'),
        'por_subtono_usuaria': grupos('undertone'),
        'confianza': {'n': len(pares), 'antes': round(antes, 2) if antes else None,
                      'despues': round(despues, 2) if despues else None, 'cambio_pct': cambio},
        'kr': {'kr1_utiles_pct': tono['acierto_pct'], 'kr2_cambio_confianza_pct': cambio,
               'kr3_interaccion_pct': round(data.usuarias_activas / data.usuarias * 100) if data.usuarias else None},
        'tonos_con_mas_fallos': sorted(fallos.values(), key=lambda f: -f['n'])[:5],
    }


@router.post('/api/panel')
def panel(payload: PanelPayload):
    return panel_resultados(payload)
