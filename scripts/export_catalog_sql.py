"""Genera supabase/migrations/006_catalogo_inicial.sql a partir de data/productos_mvp.csv.

Uso (desde la carpeta del backend):  python scripts/export_catalog_sql.py
El SQL inserta los productos que falten y no toca los que ya existan (ni los que editó una administradora).
"""
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / 'data' / 'productos_mvp.csv'
OUT = ROOT / 'supabase' / 'migrations' / '006_catalogo_inicial.sql'
COLUMNS = ['id', 'nombre', 'marca', 'categoria', 'tono', 'profundidad', 'subtono', 'acabado', 'color_hex', 'precio_cop',
           'tipos_piel', 'estacion', 'descripcion', 'imagen', 'nivel', 'calidad', 'fuente', 'precio_fuente', 'tienda',
           'tienda_url', 'enlace_tipo', 'panes', 'origen_color']


def literal(value: str, column: str) -> str:
    if column == 'precio_cop':
        return str(int(value))
    return "'" + (value or '').replace("'", "''") + "'"


def main() -> int:
    with CSV.open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        if not re.fullmatch(r'CH-[0-9]{3,5}', r['id']):
            raise SystemExit(f"Id inválido: {r['id']}")
        if not re.fullmatch(r'#[0-9A-Fa-f]{6}', r['color_hex']):
            raise SystemExit(f"Color inválido en {r['id']}: {r['color_hex']}")
    lines = [
        f'-- Catálogo inicial: {len(rows)} productos del MVP (generado por scripts/export_catalog_sql.py; no editar a mano).',
        '-- Ejecutar después de 005_catalogo_pagos.sql. Se puede repetir: solo agrega los que falten.',
        f"insert into public.catalog_products ({', '.join(COLUMNS)}) values",
    ]
    values = ['  (' + ', '.join(literal(r[c], c) for c in COLUMNS) + ')' for r in rows]
    lines.append(',\n'.join(values))
    lines.append('on conflict (id) do nothing;')
    lines.append('')
    lines.append('-- Los productos nuevos de la app siguen numerando después del mayor id existente.')
    lines.append("select setval('public.catalog_product_seq', greatest((select max(substring(id from 4)::int) from public.catalog_products), 8000));")
    OUT.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'{len(rows)} productos → {OUT.relative_to(ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
