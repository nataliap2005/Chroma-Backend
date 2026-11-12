"""Auditoría sin efectos secundarios del snapshot de productos Chroma."""
from __future__ import annotations
import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data" / "productos_mvp.csv"
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def audit(rows: list[dict[str, str]]) -> dict:
    ids = [r.get("id", "").strip() for r in rows]
    counts = Counter(ids)
    fields = ("id", "nombre", "marca", "categoria", "tono")
    return {
        "total": len(rows),
        "duplicate_ids": sorted(k for k, n in counts.items() if k and n > 1),
        "missing_id_count": sum(not i for i in ids),
        "required_fields_missing": sum(any(not r.get(k, "").strip() for k in fields) for r in rows),
        "invalid_hex_ids": [r.get("id") for r in rows if r.get("color_hex", "") and not HEX.fullmatch(r["color_hex"])],
        "invalid_price_ids": [r.get("id") for r in rows if not r.get("precio_cop", "").isdigit() or int(r["precio_cop"]) < 0],
        "missing_image_reference_count": sum(not r.get("imagen", "").strip() for r in rows),
        "image_paths_outside_public_pattern": [r.get("id") for r in rows if r.get("imagen", "") and not r["imagen"].startswith("/static/img/products/")],
        "missing_source_url_count": sum(not r.get("fuente", "").strip() for r in rows),
        "missing_store_url_count": sum(not r.get("tienda_url", "").strip() for r in rows),
        "quality_levels": dict(sorted(Counter(r.get("nivel", "") for r in rows).items())),
        "categories": dict(sorted(Counter(r.get("categoria", "") for r in rows).items())),
        "notes": "No verifica HTTP, licencia de imágenes ni vigencia de precios; imágenes deben validarse en frontend."
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path, help="Salida opcional del reporte")
    args = parser.parse_args()
    with CATALOG.open(encoding="utf-8-sig", newline="") as f:
        records = list(csv.DictReader(f))
    result = audit(records)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
