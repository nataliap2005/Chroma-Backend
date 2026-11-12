"""Las pruebas no se conectan a Supabase aunque el .env tenga sus datos: los planes se simulan."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import plans  # noqa: E402


@pytest.fixture(autouse=True)
def planes_desactivados():
    plans.set_gateway(None)
    yield
    plans.set_gateway(None)
