"""Las pruebas no se conectan a Supabase, Wompi ni Resend aunque el .env tenga sus datos:
los planes y los pagos se simulan y el catálogo se lee del CSV."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import catalog_service  # noqa: E402
import payments  # noqa: E402
import plans  # noqa: E402


@pytest.fixture(autouse=True)
def servicios_simulados(monkeypatch):
    for name in ('RESEND_API_KEY', 'WOMPI_PUBLIC_KEY', 'WOMPI_INTEGRITY_SECRET', 'WOMPI_EVENTS_SECRET',
                 'CHROMA_SUPABASE_SERVICE_ROLE_KEY', 'CHROMA_APP_URL', 'CHROMA_PRICE_PLUS', 'CHROMA_PRICE_PREMIUM'):
        monkeypatch.delenv(name, raising=False)
    plans.set_gateway(None)
    payments.set_backend(None)
    catalog_service.set_source('csv')
    yield
    plans.set_gateway(None)
    payments.set_backend(None)
    catalog_service.set_source(None)
