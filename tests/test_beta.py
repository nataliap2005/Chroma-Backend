"""Pagos con Wompi (simulados), catálogo desde Supabase y alternativas por plan."""
import hashlib

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import catalog_service
import emails
import payments
import plans
from app import app
from tests.test_plans import FakeGateway, auth

client = TestClient(app)
USER = {'id': '11111111-1111-1111-1111-111111111111', 'email': 'ana@example.com'}


class FakeBackend:
    """Supabase + Wompi en memoria, con la misma lógica que apply_payment() de la migración 005."""

    def __init__(self):
        self.payments = {}
        self.plans = {}
        self.transactions = {}

    def user(self, token):
        if token != 'tok-ana':
            raise HTTPException(401, 'Tu sesión expiró.')
        return USER

    def create_payment(self, row):
        self.payments[row['reference']] = dict(row)

    def payment(self, reference):
        return self.payments.get(reference)

    def apply(self, reference, status, transaction_id, method):
        pay = self.payments[reference]
        if pay['status'] == 'APPROVED':
            return {'status': 'APPROVED', 'repetido': True}
        pay.update(status=status, wompi_transaction_id=transaction_id)
        if status == 'APPROVED':
            self.plans[pay['user_id']] = self.plans.get(pay['user_id'], 0) + 30
        return {'status': status, 'repetido': False, 'hasta': '2026-12-17T00:00:00Z'}

    def user_email(self, user_id):
        return USER['email']

    def transaction(self, transaction_id):
        if transaction_id not in self.transactions:
            raise HTTPException(404, 'Wompi no encontró esa transacción.')
        return self.transactions[transaction_id]


@pytest.fixture
def pay(monkeypatch):
    for k, v in {'WOMPI_PUBLIC_KEY': 'pub_test_abc', 'WOMPI_INTEGRITY_SECRET': 'test_integrity_x',
                 'WOMPI_EVENTS_SECRET': 'test_events_y', 'CHROMA_SUPABASE_URL': 'https://x.supabase.co',
                 'CHROMA_SUPABASE_PUBLISHABLE_KEY': 'pk', 'CHROMA_SUPABASE_SERVICE_ROLE_KEY': 'sk',
                 'CHROMA_APP_URL': 'https://app.chroma.test'}.items():
        monkeypatch.setenv(k, v)
    sent = []
    monkeypatch.setattr(emails, 'payment_approved', lambda *a: sent.append(a) or True)
    fake = FakeBackend()
    fake.sent = sent
    payments.set_backend(fake)
    return fake


def signed_event(transaction, secret='test_events_y', timestamp=1700000000):
    props = ['transaction.id', 'transaction.status', 'transaction.amount_in_cents']
    raw = f"{transaction['id']}{transaction['status']}{transaction['amount_in_cents']}{timestamp}{secret}"
    return {'event': 'transaction.updated', 'data': {'transaction': transaction}, 'timestamp': timestamp,
            'signature': {'properties': props, 'checksum': hashlib.sha256(raw.encode()).hexdigest().upper()}}


def test_payments_off_without_keys():
    assert client.get('/api/payments/config').json()['activos'] is False
    r = client.post('/api/payments/checkout', json={'plan': 'plus'}, headers=auth('tok-ana'))
    assert r.status_code == 503
    assert client.get('/health').json()['pagos'].startswith('desactivados')


def test_config_prices_from_financial_model(pay):
    cfg = client.get('/api/payments/config').json()
    assert cfg['activos'] and cfg['pruebas']
    assert cfg['precios'] == {'plus': 19900, 'premium': 34900}


def test_checkout_needs_login_and_signs(pay):
    assert client.post('/api/payments/checkout', json={'plan': 'plus'}).status_code == 401
    assert client.post('/api/payments/checkout', json={'plan': 'oro'}, headers=auth('tok-ana')).status_code == 422
    r = client.post('/api/payments/checkout', json={'plan': 'premium'}, headers=auth('tok-ana')).json()
    ref = r['reference']
    assert pay.payments[ref]['amount_in_cents'] == 3_490_000 and pay.payments[ref]['status'] == 'PENDING'
    url = httpx.URL(r['checkout_url'])
    assert url.host == 'checkout.wompi.co'
    q = url.params
    assert q['amount-in-cents'] == '3490000' and q['currency'] == 'COP' and q['reference'] == ref
    assert q['redirect-url'] == 'https://app.chroma.test/planes'
    assert q['signature:integrity'] == hashlib.sha256(f'{ref}3490000COPtest_integrity_x'.encode()).hexdigest()


def test_webhook_activates_plan_once(pay):
    ref = client.post('/api/payments/checkout', json={'plan': 'plus'}, headers=auth('tok-ana')).json()['reference']
    tx = {'id': 'tx-1', 'reference': ref, 'status': 'APPROVED', 'amount_in_cents': 1_990_000, 'currency': 'COP',
          'payment_method_type': 'CARD', 'customer_email': 'ana@example.com'}
    assert client.post('/api/payments/wompi/webhook', json={**signed_event(tx), 'timestamp': 1}).status_code == 401
    r = client.post('/api/payments/wompi/webhook', json=signed_event(tx))
    assert r.status_code == 200 and r.json()['status'] == 'APPROVED'
    client.post('/api/payments/wompi/webhook', json=signed_event(tx))   # Wompi repite el evento
    assert pay.plans[USER['id']] == 30
    assert len(pay.sent) == 1 and pay.sent[0][0] == 'ana@example.com'


def test_webhook_rejects_wrong_amount(pay):
    ref = client.post('/api/payments/checkout', json={'plan': 'premium'}, headers=auth('tok-ana')).json()['reference']
    tx = {'id': 'tx-2', 'reference': ref, 'status': 'APPROVED', 'amount_in_cents': 100, 'currency': 'COP'}
    assert client.post('/api/payments/wompi/webhook', json=signed_event(tx)).json()['status'] == 'ERROR'
    assert USER['id'] not in pay.plans


def test_webhook_ignores_unknown_reference(pay):
    tx = {'id': 'tx-9', 'reference': 'OTRA', 'status': 'APPROVED', 'amount_in_cents': 100}
    assert client.post('/api/payments/wompi/webhook', json=signed_event(tx)).json()['ignorado']


def test_status_on_return_checks_wompi(pay):
    ref = client.post('/api/payments/checkout', json={'plan': 'plus'}, headers=auth('tok-ana')).json()['reference']
    pay.transactions['tx-3'] = {'id': 'tx-3', 'reference': ref, 'status': 'PENDING', 'amount_in_cents': 1_990_000}
    assert client.get('/api/payments/status?id=tx-3', headers=auth('tok-ana')).json()['status'] == 'PENDING'
    pay.transactions['tx-3']['status'] = 'APPROVED'
    assert client.get('/api/payments/status?id=tx-3', headers=auth('tok-ana')).json()['status'] == 'APPROVED'
    assert pay.plans[USER['id']] == 30
    assert client.get('/api/payments/status?id=tx-3').status_code == 401
    pay.payments[ref]['user_id'] = 'otra'
    assert client.get('/api/payments/status?id=tx-3', headers=auth('tok-ana')).status_code == 404


def test_translator_alternatives_by_plan():
    fake = FakeGateway({'tok-free': 'free', 'tok-premium': 'premium'})
    plans.set_gateway(fake)
    base = next(p for p in client.get('/api/products').json()['products'] if p['categoria'] == 'Labial')
    free = client.get(f"/api/translator?product_id={base['id']}&limit=20", headers=auth('tok-free'))
    premium = client.get(f"/api/translator?product_id={base['id']}&limit=20", headers=auth('tok-premium'))
    assert free.status_code == 200 and premium.status_code == 200
    assert len(free.json()['results']) <= 5
    assert len(premium.json()['results']) <= 15


def test_catalog_from_supabase_with_fallback(monkeypatch):
    monkeypatch.setenv('CHROMA_SUPABASE_URL', 'https://x.supabase.co')
    monkeypatch.setenv('CHROMA_SUPABASE_PUBLISHABLE_KEY', 'pk')
    catalog_service.set_source(None)
    row = {c: '' for c in catalog_service.COLUMNS}
    row.update(id='CH-8001', nombre='Labial nuevo', marca='Vogue', categoria='Labial', color_hex='#AA3344', precio_cop=25000, tono=None)
    monkeypatch.setattr(catalog_service, 'fetch_supabase_catalog', lambda: [row])
    data = client.get('/api/products').json()
    assert data['catalog_status'] == 'supabase'
    assert [p['id'] for p in data['products']] == ['CH-8001'] and data['products'][0]['tono'] == ''

    def boom():
        raise httpx.ConnectError('sin red')
    catalog_service.set_source(None)
    monkeypatch.setattr(catalog_service, 'fetch_supabase_catalog', boom)
    assert len(client.get('/api/products').json()['products']) == 688   # cae al CSV


def test_service_key_headers(monkeypatch):
    monkeypatch.setenv('CHROMA_SUPABASE_URL', 'https://x.supabase.co')
    monkeypatch.setenv('CHROMA_SUPABASE_SERVICE_ROLE_KEY', 'eyJ.clasica.jwt')
    assert payments.LiveBackend()._service_headers()['Authorization'] == 'Bearer eyJ.clasica.jwt'
    monkeypatch.setenv('CHROMA_SUPABASE_SERVICE_ROLE_KEY', 'sb_secret_nueva')
    headers = payments.LiveBackend()._service_headers()
    assert headers['apikey'] == 'sb_secret_nueva' and 'Authorization' not in headers
