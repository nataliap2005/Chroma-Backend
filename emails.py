"""Correos de Chroma con Resend (https://resend.com).

- Los correos de cuenta (confirmar registro, recuperar contraseña) los manda Supabase Auth.
  Para que salgan desde el dominio de Chroma, se configura Resend como SMTP en Supabase
  (ver README). No pasan por esta API.
- Esta API solo manda la confirmación de pago. Sin RESEND_API_KEY no se manda nada (y no falla).
"""
import html
import logging
import os

import httpx

log = logging.getLogger("chroma.emails")


def configured() -> bool:
    return bool(os.environ.get("RESEND_API_KEY", "").strip())


def send(to: str, subject: str, body_html: str) -> bool:
    key = os.environ.get("RESEND_API_KEY", "").strip()
    sender = os.environ.get("CHROMA_EMAIL_FROM", "").strip() or "Chroma <onboarding@resend.dev>"
    if not key or not to:
        return False
    try:
        r = httpx.post("https://api.resend.com/emails", timeout=10,
                       headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                       json={"from": sender, "to": [to], "subject": subject, "html": body_html})
        if r.status_code >= 400:
            log.warning("Resend respondió %s: %s", r.status_code, r.text[:300])
            return False
        return True
    except httpx.HTTPError as exc:
        log.warning("No se pudo enviar el correo: %s", exc)
        return False


def cop(amount: int) -> str:
    return f"COP ${amount:,.0f}".replace(",", ".")


def payment_approved(to: str, plan_name: str, amount_cop: int, until: str, reference: str) -> bool:
    fecha = html.escape(until[:10]) if until else ""
    hasta = f" hasta el <strong>{fecha}</strong>" if fecha else ""
    body = f"""
    <div style="font-family:Arial,sans-serif;max-width:520px;margin:auto;color:#2b2330">
      <h2 style="color:#8a4f7d">¡Ya tienes Chroma {html.escape(plan_name)}!</h2>
      <p>Recibimos tu pago de <strong>{cop(amount_cop)}</strong>.</p>
      <p>Tu plan {html.escape(plan_name)} está activo{hasta}.
         Abre la app para usar las marcas, consultas y looks de tu plan.</p>
      <p style="color:#777;font-size:12px">Referencia del pago: {html.escape(reference)}<br>
         Versión beta de Chroma. Si no reconoces este pago, responde este correo.</p>
    </div>"""
    return send(to, f"Tu plan Chroma {plan_name} está activo", body)
