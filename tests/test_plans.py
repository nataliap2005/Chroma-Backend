"""Planes Free, Plus y Premium: candado por marca, cuotas y conexión con Supabase (simulada)."""
import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import plans
from app import app

client = TestClient(app)
MARCAS = {'Essence': 'plus', 'Estée Lauder': 'premium'}
LIMITES = {'free': (10, 4), 'plus': (100, 60), 'premium': (300, 180)}


class FakeGateway:
    """Hace lo mismo que las funciones my_plan() y consume_quota() de la migración 004."""

    def __init__(self, planes):
        self.planes = planes            # token -> plan
        self.uso = {}

    def _info(self, token):
        plan = self.planes.get(token, 'free')
        t, lk = self.uso.get(token, (0, 0))
        return {'plan': plan, 'nombre': plans.NOMBRE[plan], 'marcas': MARCAS, 'sesion': token is not None,
                'traductor': {'usadas': t, 'limite': LIMITES[plan][0]}, 'looks': {'usados': lk, 'limite': LIMITES[plan][1]}}

    def my_plan(self, token):
        return self._info(token)

    def consume(self, token, tipo):
        if not token:
            raise HTTPException(401, 'Inicia sesión')
        t, lk = self.uso.get(token, (0, 0))
        info = self._info(token)
        if (t if tipo == 'traductor' else lk) >= info[tipo]['limite']:
            raise HTTPException(429, 'Ya usaste tu cuota')
        self.uso[token] = (t + 1, lk) if tipo == 'traductor' else (t, lk + 1)
        return self._info(token)


@pytest.fixture
def gw():
    fake = FakeGateway({'tok-free': 'free', 'tok-plus': 'plus', 'tok-premium': 'premium'})
    plans.set_gateway(fake)
    yield fake
    plans.set_gateway(None)


def auth(token):
    return {'Authorization': f'Bearer {token}'}


def answers():
    questions = client.get('/api/questionnaire').json()['questions']
    data = {q['key']: q['options'][-1]['value'] for q in questions}
    data.update(skin_tone='medio', budget='120000')
    return data


def lock(products, marca):
    return {p['bloqueado'] for p in products if p['marca'] == marca}


def test_without_supabase_plans_are_off():
    plans.set_gateway(None)
    data = client.post('/api/products/personalized', json={}).json()
    assert not any(p['bloqueado'] for p in data['products'])
    assert client.get('/api/translator', params={'product_id': 'CH-5109'}).status_code == 200


def test_locks_by_plan(gw):
    free = client.post('/api/products/personalized', json={}).json()['products']     # sin sesión = Free
    assert lock(free, 'Essence') == {True} and lock(free, 'Estée Lauder') == {True} and lock(free, 'Vogue') == {False}
    assert {p['plan_requerido'] for p in free if p['marca'] == 'Essence'} == {'Plus'}
    plus = client.post('/api/products/personalized', json={}, headers=auth('tok-plus')).json()['products']
    assert lock(plus, 'Essence') == {False} and lock(plus, 'Estée Lauder') == {True}
    premium = client.post('/api/products/personalized', json={}, headers=auth('tok-premium')).json()['products']
    assert not any(p['bloqueado'] for p in premium)


def test_translator_needs_login_and_counts(gw):
    assert client.get('/api/translator', params={'product_id': 'CH-5109'}).status_code == 401
    for i in range(10):
        r = client.get('/api/translator', params={'product_id': 'CH-5109'}, headers=auth('tok-free'))
        assert r.status_code == 200, r.text
    assert r.json()['plan']['traductor'] == {'usadas': 10, 'limite': 10}
    r = client.get('/api/translator', params={'product_id': 'CH-5109'}, headers=auth('tok-free'))
    assert r.status_code == 429


def test_failed_translation_does_not_spend(gw):
    r = client.get('/api/translator', params={'product_id': 'NO-EXISTE'}, headers=auth('tok-free'))
    assert r.status_code == 422
    assert gw.uso.get('tok-free') is None


def test_advisor_quota_and_locked_brands(gw):
    body = {'occasion': 'noche', 'budget': 5_000_000, 'answers': answers()}
    assert client.post('/api/advisor', json=body).status_code == 401
    for _ in range(4):
        r = client.post('/api/advisor', json=body, headers=auth('tok-free'))
        assert r.status_code == 200, r.text
        marcas = {i['product']['marca'] for i in r.json()['items'] if i.get('product')}
        assert not marcas & {'Essence', 'Estée Lauder'}
    assert r.json()['plan']['looks'] == {'usados': 4, 'limite': 4}
    assert client.post('/api/advisor', json=body, headers=auth('tok-free')).status_code == 429


def test_supabase_gateway_maps_errors(monkeypatch):
    calls = []

    def fake_post(url, json, headers, timeout):
        calls.append((url, json, headers))
        if url.endswith('consume_quota'):
            return httpx.Response(429, json={'message': 'Ya usaste 10 consultas al traductor de tu plan Free este mes.'})
        return httpx.Response(200, json={'plan': 'free', 'marcas': MARCAS})

    monkeypatch.setattr(plans.httpx, 'post', fake_post)
    g = plans.SupabaseGateway('https://demo.supabase.co/', 'sb_publishable_x')
    assert g.my_plan(None)['plan'] == 'free'
    assert calls[0][0] == 'https://demo.supabase.co/rest/v1/rpc/my_plan' and 'Authorization' not in calls[0][2]
    with pytest.raises(HTTPException) as e:
        g.consume('tok', 'traductor')
    assert e.value.status_code == 429 and 'Ya usaste' in e.value.detail
    assert calls[1][2]['Authorization'] == 'Bearer tok' and calls[1][1] == {'p_tipo': 'traductor'}
    with pytest.raises(HTTPException) as e:
        g.consume(None, 'looks')
    assert e.value.status_code == 401
