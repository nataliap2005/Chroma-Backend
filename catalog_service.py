"""Operaciones de lectura sobre el catálogo CSV existente de Chroma.

Este módulo NO altera el motor de colorimetría de Natalia ni guarda usuarios.
"""
import csv
from collections import Counter
from pathlib import Path
from typing import Any

CATALOG_FILE = Path(__file__).resolve().parent / "data" / "productos_mvp.csv"


def load_catalog(path: Path = CATALOG_FILE) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        records = list(csv.DictReader(handle))
    result = []
    for record in records:
        item = dict(record)
        try:
            item["precio_cop"] = int(item["precio_cop"])
        except (ValueError, TypeError, KeyError) as exc:
            raise ValueError(f"Precio inválido en producto {item.get('id', '?')}") from exc
        result.append(item)
    return result


def search_catalog(
    items: list[dict[str, Any]], *, q: str = "", category: str = "", brand: str = "",
    max_price: int | None = None, offset: int = 0, limit: int = 24,
) -> dict[str, Any]:
    query = q.strip().casefold()
    filtered = [p for p in items if (
        (not query or query in " ".join(str(p.get(k, "")) for k in ("nombre", "marca", "tono")).casefold())
        and (not category or str(p.get("categoria", "")).casefold() == category.casefold())
        and (not brand or str(p.get("marca", "")).casefold() == brand.casefold())
        and (max_price is None or p["precio_cop"] <= max_price)
    )]
    filtered.sort(key=lambda p: (str(p.get("marca", "")).casefold(), str(p.get("nombre", "")).casefold(), str(p.get("tono", "")).casefold()))
    return {"products": filtered[offset:offset + limit], "total": len(filtered), "offset": offset, "limit": limit, "catalog_status": "mvp_snapshot"}


def catalog_facets(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {"total": len(items),
            "categories": dict(sorted(Counter(p.get("categoria", "") for p in items).items())),
            "brands": dict(sorted(Counter(p.get("marca", "") for p in items).items()))}
