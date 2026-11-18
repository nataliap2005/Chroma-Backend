"""catálogo personalizado, opiniones que ajustan la compatibilidad y panel."""
from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def answers():
    questions = client.get('/api/questionnaire').json()['questions']
    data = {q['key']: q['options'][-1]['value'] for q in questions}
    data.update(skin_tone='medio', budget='120000', finish='satinado', skin_type='mixta')
    return data


def test_catalog_without_profile_has_no_score():
    r = client.post('/api/products/personalized', json={})
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data['products']) == 688 and data['personalized'] is False
    assert all(p['compatibilidad']['score'] is None for p in data['products'])


def test_catalog_with_profile_scores_and_factors():
    data = client.post('/api/products/personalized', json={'answers': answers()}).json()
    assert data['personalized'] is True
    scores = [p['compatibilidad']['score'] for p in data['products']]
    assert all(0 <= s <= 100 for s in scores)
    assert {f['label'] for f in data['products'][0]['compatibilidad']['factors']} >= {'Subtono', 'Presupuesto'}


def test_ids_filter_and_favorites():
    data = client.post('/api/products/personalized',
                       json={'ids': ['CH-5109', 'CH-5265'], 'favorites': ['CH-5109']}).json()
    assert sorted(p['id'] for p in data['products']) == ['CH-5109', 'CH-5265']
    assert {p['id']: p['favorito'] for p in data['products']} == {'CH-5109': True, 'CH-5265': False}


def test_incorrect_tone_lowers_score():
    base = client.post('/api/products/personalized', json={'answers': answers(), 'ids': ['CH-5109']}).json()
    after = client.post('/api/products/personalized', json={
        'answers': answers(), 'ids': ['CH-5109'],
        'feedback': {'CH-5109': {'tono_resultado': 'incorrecto'}}}).json()
    before_score = base['products'][0]['compatibilidad']['score']
    compat = after['products'][0]['compatibilidad']
    assert compat['score'] < before_score
    assert 'no te funcionó' in compat['messages'][0]


def test_invalid_opinion_is_rejected():
    r = client.post('/api/products/personalized', json={'feedback': {'CH-5109': {'tono_resultado': 'regular'}}})
    assert r.status_code == 422


def test_advisor_uses_vanity_and_feedback():
    r = client.post('/api/advisor', json={
        'occasion': 'universidad', 'budget': 1_000_000, 'answers': answers(),
        'owned_ids': ['CH-5001'], 'feedback': {'CH-5109': {'tono_resultado': 'acertado'}}})
    assert r.status_code == 200, r.text
    assert r.json()['owns'] >= 1


def test_advisor_night_has_eye_guide():
    r = client.post('/api/advisor', json={'occasion': 'noche', 'budget': 1_000_000, 'answers': answers()})
    sombras = next(i for i in r.json()['items'] if i['category'] == 'Sombras')
    assert sombras['aplicacion']


def test_panel_matches_alpha_rules():
    payload = {
        'usuarias': 10, 'con_perfil': 8, 'usuarias_con_feedback': 3, 'usuarias_activas': 5,
        'evaluaciones': [
            {'product_id': 'CH-5109', 'tono_resultado': 'incorrecto', 'motivo_tono': 'muy_claro',
             'forma_evaluacion': 'probado', 'confidence_before': 2, 'confidence_after': 3, 'undertone': 'frio'},
            {'product_id': 'CH-5265', 'tono_resultado': 'acertado', 'forma_evaluacion': 'pantalla',
             'confidence_before': 2, 'confidence_after': 4, 'undertone': 'calido'},
            {'product_id': 'CH-5109', 'tono_resultado': 'parcial', 'motivo_tono': 'acabado',
             'forma_evaluacion': 'probado'},
            {'product_id': 'NO-EXISTE', 'tono_resultado': 'acertado'},
        ]}
    r = client.post('/api/panel', json=payload)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d['evaluaciones'] == 3
    assert d['tono'] == {'n': 3, 'acertado': 1, 'parcial': 1, 'incorrecto': 1, 'acierto_pct': 67, 'acertado_pct': 33}
    assert d['motivos'] == {'El acabado': 1, 'Muy claro': 1}
    assert d['forma'] == {'pantalla': 1, 'probado': 2}
    assert d['confianza'] == {'n': 2, 'antes': 2.0, 'despues': 3.5, 'cambio_pct': 75}
    assert d['kr'] == {'kr1_utiles_pct': 67, 'kr2_cambio_confianza_pct': 75, 'kr3_interaccion_pct': 50}
    assert d['tonos_con_mas_fallos'][0]['id'] == 'CH-5109'
    assert 'B' in d['por_nivel'] and 'frio' in d['por_subtono_usuaria']
