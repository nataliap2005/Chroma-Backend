"""Pagos de Plus y Premium con Wompi (Web Checkout) y la migración 005 de Supabase.

Flujo:
1. La app llama POST /api/payments/checkout con el plan. La API identifica a la usuaria con su
   token de Supabase, registra el pago como PENDING y devuelve la URL del checkout de Wompi
   firmada (firma de integridad).
2. La usuaria paga en Wompi y vuelve a la app (redirect-url) con ?id=<transacción>.
3. El plan se activa por dos caminos (el que llegue primero; el otro no suma dos veces):
   - Wompi avisa a POST /api/payments/wompi/webhook (evento firmado con el secreto de eventos).
   - La app consulta GET /api/payments/status?id=<transacción>: la API pregunta a Wompi
     el estado real de la transacción (no confía en lo que diga el navegador).
   Un pago aprobado da 30 días del plan (función apply_payment de Supabase).

Variables (.env / Render): WOMPI_PUBLIC_KEY, WOMPI_INTEGRITY_SECRET, WOMPI_EVENTS_SECRET,
CHROMA_APP_URL (adonde vuelve la usuaria), CHROMA_SUPABASE_SERVICE_ROLE_KEY (solo servidor),
y opcionales CHROMA_PRICE_PLUS / CHROMA_PRICE_PREMIUM (COP). Sin ellas los pagos quedan desactivados.
"""
import hashlib
import hmac
import logging
import os
import secrets
import time
from typing import Any, Literal, Protocol
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import BaseModel

import emails
import plans

log = logging.getLogger("chroma.payments")
router = APIRouter(prefix="/api/payments", tags=["pagos"])

# Precios candidatos del modelo financiero (hoja 05 PLANES), en COP al mes.
DEFAULT_PRICES = {"plus": 19_900, "premium": 34_900}
NOMBRE = {"plus": "Plus", "premium": "Premium"}
CHECKOUT_URL = "https://checkout.wompi.co/p/"


def prices() -> dict[str, int]:
    out = {}
    for plan, default in DEFAULT_PRICES.items():
        raw = os.environ.get(f"CHROMA_PRICE_{plan.upper()}", "").strip()
        out[plan] = int(raw) if raw.isdigit() and int(raw) > 0 else default
    return out


def env(name: str) -> str:
    return os.environ.get(name, "").strip()


def wompi_api_base(public_key: str) -> str:
    return "https://sandbox.wompi.co/v1" if public_key.startswith("pub_test_") else "https://production.wompi.co/v1"


def integrity_signature(reference: str, amount_in_cents: int, currency: str, secret: str) -> str:
    return hashlib.sha256(f"{reference}{amount_in_cents}{currency}{secret}".encode()).hexdigest()


def event_checksum(event: dict[str, Any], secret: str) -> str:
    """Firma de un evento de Wompi: valores de signature.properties (dentro de data) + timestamp + secreto."""
    data = event.get("data") or {}
    values = []
    for path in (event.get("signature") or {}).get("properties") or []:
        value: Any = data
        for part in str(path).split("."):
            value = value.get(part) if isinstance(value, dict) else None
        values.append("" if value is None else str(value))
    return hashlib.sha256(("".join(values) + str(event.get("timestamp", "")) + secret).encode()).hexdigest()


def valid_event(event: dict[str, Any], secret: str) -> bool:
    checksum = str((event.get("signature") or {}).get("checksum", ""))
    return bool(secret and checksum) and hmac.compare_digest(event_checksum(event, secret).lower(), checksum.lower())


class Backend(Protocol):
    """Lo que el módulo necesita de Supabase y Wompi (se reemplaza en las pruebas)."""
    def user(self, token: str) -> dict[str, Any]: ...
    def create_payment(self, row: dict[str, Any]) -> None: ...
    def payment(self, reference: str) -> dict[str, Any] | None: ...
    def apply(self, reference: str, status: str, transaction_id: str, method: str) -> dict[str, Any]: ...
    def user_email(self, user_id: str) -> str: ...
    def transaction(self, transaction_id: str) -> dict[str, Any]: ...


class LiveBackend:
    def __init__(self) -> None:
        self.url = env("CHROMA_SUPABASE_URL").rstrip("/")
        self.anon = env("CHROMA_SUPABASE_PUBLISHABLE_KEY")
        self.service = env("CHROMA_SUPABASE_SERVICE_ROLE_KEY")
        self.wompi = wompi_api_base(env("WOMPI_PUBLIC_KEY"))

    def _service_headers(self) -> dict[str, str]:
        headers = {"apikey": self.service, "Content-Type": "application/json"}
        # La clave service_role clásica es un JWT y también va como Bearer; las claves nuevas
        # (sb_secret_…) no son JWT y Supabase las acepta solo en el encabezado apikey.
        if not self.service.startswith("sb_secret_"):
            headers["Authorization"] = f"Bearer {self.service}"
        return headers

    def _check(self, r: httpx.Response, what: str) -> httpx.Response:
        if r.status_code >= 400:
            log.error("%s falló (%s): %s", what, r.status_code, r.text[:300])
            raise HTTPException(502, f"No se pudo {what}. Intenta de nuevo en un momento.")
        return r

    def user(self, token: str) -> dict[str, Any]:
        try:
            r = httpx.get(f"{self.url}/auth/v1/user", headers={"apikey": self.anon, "Authorization": f"Bearer {token}"}, timeout=8)
        except httpx.HTTPError as exc:
            raise HTTPException(503, "No se pudo verificar tu sesión.") from exc
        if r.status_code in (401, 403):
            raise HTTPException(401, "Tu sesión expiró. Vuelve a iniciar sesión.")
        return self._check(r, "verificar tu sesión").json()

    def create_payment(self, row: dict[str, Any]) -> None:
        r = httpx.post(f"{self.url}/rest/v1/payments", json=row,
                       headers={**self._service_headers(), "Prefer": "return=minimal"}, timeout=8)
        self._check(r, "registrar el pago")

    def payment(self, reference: str) -> dict[str, Any] | None:
        r = httpx.get(f"{self.url}/rest/v1/payments", params={"reference": f"eq.{reference}", "select": "*"},
                      headers=self._service_headers(), timeout=8)
        rows = self._check(r, "consultar el pago").json()
        return rows[0] if rows else None

    def apply(self, reference: str, status: str, transaction_id: str, method: str) -> dict[str, Any]:
        r = httpx.post(f"{self.url}/rest/v1/rpc/apply_payment", headers=self._service_headers(), timeout=8,
                       json={"p_reference": reference, "p_status": status, "p_transaction_id": transaction_id, "p_method": method})
        return self._check(r, "activar el plan").json()

    def user_email(self, user_id: str) -> str:
        try:
            r = httpx.get(f"{self.url}/auth/v1/admin/users/{user_id}", headers=self._service_headers(), timeout=8)
            return r.json().get("email", "") if r.status_code < 400 else ""
        except httpx.HTTPError:
            return ""

    def transaction(self, transaction_id: str) -> dict[str, Any]:
        try:
            r = httpx.get(f"{self.wompi}/transactions/{transaction_id}", timeout=10)
        except httpx.HTTPError as exc:
            raise HTTPException(503, "No se pudo consultar el pago en Wompi.") from exc
        if r.status_code == 404:
            raise HTTPException(404, "Wompi no encontró esa transacción.")
        return self._check(r, "consultar el pago en Wompi").json().get("data") or {}


_backend: Backend | None = None


def configured() -> bool:
    return all(env(n) for n in ("WOMPI_PUBLIC_KEY", "WOMPI_INTEGRITY_SECRET", "CHROMA_SUPABASE_URL",
                                "CHROMA_SUPABASE_PUBLISHABLE_KEY", "CHROMA_SUPABASE_SERVICE_ROLE_KEY"))


def backend() -> Backend:
    global _backend
    if _backend is None:
        if not configured():
            raise HTTPException(503, "Los pagos todavía no están activos en esta versión de prueba.")
        _backend = LiveBackend()
    return _backend


def set_backend(b: Backend | None) -> None:
    """Para pruebas."""
    global _backend
    _backend = b


def settle(transaction: dict[str, Any]) -> dict[str, Any]:
    """Aplica el estado de una transacción de Wompi a su pago. Comprueba monto y moneda."""
    b = backend()
    reference = str(transaction.get("reference", ""))
    pay = b.payment(reference)
    if not pay:
        raise HTTPException(404, "Pago desconocido.")
    status = str(transaction.get("status", "")).upper()
    if status not in ("APPROVED", "DECLINED", "VOIDED", "ERROR", "PENDING"):
        raise HTTPException(422, "Estado de pago desconocido.")
    if status == "APPROVED" and (int(transaction.get("amount_in_cents") or 0) != int(pay["amount_in_cents"])
                                 or transaction.get("currency", "COP") != pay.get("currency", "COP")):
        log.error("Monto distinto en %s: Wompi %s, esperado %s", reference, transaction.get("amount_in_cents"), pay["amount_in_cents"])
        status = "ERROR"
    if status == "PENDING" or pay.get("status") == "APPROVED":
        return {"reference": reference, "status": pay.get("status") if status == "PENDING" else "APPROVED", "plan": pay["plan"]}
    result = b.apply(reference, status, str(transaction.get("id", "")), str(transaction.get("payment_method_type", "")))
    if status == "APPROVED" and not result.get("repetido"):
        email = transaction.get("customer_email") or b.user_email(str(pay["user_id"]))
        emails.payment_approved(email, NOMBRE[pay["plan"]], int(pay["amount_in_cents"]) // 100,
                                str(result.get("hasta") or ""), reference)
    return {"reference": reference, "status": status, "plan": pay["plan"], "hasta": result.get("hasta")}


class CheckoutPayload(BaseModel):
    plan: Literal["plus", "premium"]


@router.get("/config")
def payments_config():
    """Precios y si los pagos están activos (la app lo usa para mostrar u ocultar el botón)."""
    return {"activos": configured(), "precios": prices(), "moneda": "COP", "dias": 30,
            "pruebas": env("WOMPI_PUBLIC_KEY").startswith("pub_test_")}


@router.post("/checkout")
def checkout(payload: CheckoutPayload, authorization: str | None = Header(None)):
    b = backend()
    token = plans.token_from(authorization)
    if not token:
        raise HTTPException(401, "Inicia sesión en la pestaña Cuenta para cambiar de plan.")
    user = b.user(token)
    amount = prices()[payload.plan] * 100
    reference = f"CHR-{payload.plan[:2].upper()}-{int(time.time())}-{secrets.token_hex(4)}"
    b.create_payment({"reference": reference, "user_id": user["id"], "plan": payload.plan,
                      "amount_in_cents": amount, "currency": "COP", "status": "PENDING"})
    redirect = (env("CHROMA_APP_URL") or "http://localhost:8101").rstrip("/") + "/planes"
    params = {"public-key": env("WOMPI_PUBLIC_KEY"), "currency": "COP", "amount-in-cents": amount,
              "reference": reference, "signature:integrity": integrity_signature(reference, amount, "COP", env("WOMPI_INTEGRITY_SECRET")),
              "redirect-url": redirect}
    if user.get("email"):
        params["customer-data:email"] = user["email"]
    return {"checkout_url": f"{CHECKOUT_URL}?{urlencode(params)}", "reference": reference,
            "amount_cop": amount // 100, "plan": payload.plan}


@router.get("/status")
def status(id: str = Query(..., min_length=3, max_length=80), authorization: str | None = Header(None)):
    """Estado de una transacción al volver de Wompi; si está aprobada, activa el plan."""
    b = backend()
    token = plans.token_from(authorization)
    if not token:
        raise HTTPException(401, "Inicia sesión para ver el estado de tu pago.")
    user = b.user(token)
    transaction = b.transaction(id)
    pay = b.payment(str(transaction.get("reference", "")))
    if not pay or str(pay["user_id"]) != str(user["id"]):
        raise HTTPException(404, "Ese pago no es de esta cuenta.")
    return settle(transaction)


@router.post("/wompi/webhook")
async def webhook(request: Request):
    """URL de eventos de Wompi (se registra en el panel de Wompi → Desarrolladores)."""
    try:
        event = await request.json()
    except ValueError as exc:
        raise HTTPException(400, "JSON inválido") from exc
    if not valid_event(event, env("WOMPI_EVENTS_SECRET")):
        raise HTTPException(401, "Firma inválida")
    if event.get("event") != "transaction.updated":
        return {"ok": True, "ignorado": event.get("event")}
    transaction = (event.get("data") or {}).get("transaction") or {}
    try:
        return {"ok": True, **settle(transaction)}
    except HTTPException as exc:
        if exc.status_code == 404:  # referencia que no es de Chroma: Wompi no debe reintentar
            return {"ok": True, "ignorado": "referencia desconocida"}
        raise
