"""Planes Free, Plus y Premium: marcas por plan y cuotas mensuales (migración 005 de Supabase).

La API no guarda nada ni tiene claves privadas: reenvía a Supabase el token de la usuaria y llama a
las funciones my_plan() y consume_quota(), que deciden con permisos de la propia usuaria.
Solo necesita la URL del proyecto y la clave publishable (la misma que usa la app).

Sin CHROMA_SUPABASE_URL / CHROMA_SUPABASE_PUBLISHABLE_KEY los planes quedan desactivados
(todas las marcas, sin cuotas): útil para desarrollo y pruebas, no para el alfa con usuarias.
"""
import os
from typing import Any, Protocol

import httpx
from fastapi import HTTPException

ORDEN = {'free': 0, 'plus': 1, 'premium': 2}
NOMBRE = {'free': 'Free', 'plus': 'Plus', 'premium': 'Premium'}


class Gateway(Protocol):
    def my_plan(self, token: str | None) -> dict[str, Any]: ...
    def consume(self, token: str | None, tipo: str) -> dict[str, Any]: ...


class SupabaseGateway:
    def __init__(self, url: str, key: str):
        self.url = url.rstrip('/')
        self.key = key

    def _rpc(self, name: str, token: str | None, body: dict[str, Any]) -> dict[str, Any]:
        headers = {'apikey': self.key, 'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        try:
            r = httpx.post(f'{self.url}/rest/v1/rpc/{name}', json=body, headers=headers, timeout=8)
        except httpx.HTTPError as exc:
            raise HTTPException(503, 'No se pudo verificar tu plan. Intenta de nuevo en un momento.') from exc
        if r.status_code >= 400:
            try:
                message = r.json().get('message') or ''
            except ValueError:
                message = ''
            if r.status_code == 401:
                message = message if 'sesión' in message else 'Tu sesión expiró. Vuelve a iniciar sesión.'
            raise HTTPException(r.status_code if r.status_code in (400, 401, 403, 429) else 502,
                                message or 'No se pudo verificar tu plan.')
        return r.json()

    def my_plan(self, token: str | None) -> dict[str, Any]:
        return self._rpc('my_plan', token, {})

    def consume(self, token: str | None, tipo: str) -> dict[str, Any]:
        if not token:
            raise HTTPException(401, 'Inicia sesión en la pestaña Cuenta para usar el traductor y el asesor.')
        return self._rpc('consume_quota', token, {'p_tipo': tipo})


def _from_env() -> Gateway | None:
    url = os.environ.get('CHROMA_SUPABASE_URL', '').strip()
    key = os.environ.get('CHROMA_SUPABASE_PUBLISHABLE_KEY', '').strip()
    return SupabaseGateway(url, key) if url and key else None


_gateway: Gateway | None = None
_loaded = False


def gateway() -> Gateway | None:
    global _gateway, _loaded
    if not _loaded:
        _gateway, _loaded = _from_env(), True
    return _gateway


def set_gateway(g: Gateway | None) -> None:
    """Para pruebas."""
    global _gateway, _loaded
    _gateway, _loaded = g, True


def token_from(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith('bearer '):
        return authorization[7:].strip() or None
    return None


def plan_requerido(product: dict[str, Any], plan: dict[str, Any]) -> str:
    return plan.get('marcas', {}).get(product['marca'], 'free')


def accesible(product: dict[str, Any], plan: dict[str, Any] | None) -> bool:
    if plan is None:
        return True
    return ORDEN[plan_requerido(product, plan)] <= ORDEN.get(plan.get('plan', 'free'), 0)


def mark(products: list[dict[str, Any]], plan: dict[str, Any] | None) -> None:
    """Marca con candado los productos de marcas de un plan superior (como en la versión web)."""
    for p in products:
        ok = accesible(p, plan)
        p['bloqueado'] = not ok
        p['plan_requerido'] = '' if ok else NOMBRE[plan_requerido(p, plan or {})]
