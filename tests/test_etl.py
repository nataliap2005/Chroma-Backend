"""El ETL es reproducible: a partir de las fuentes oficiales regenera exactamente el catálogo del repo.

Corre la parte que no necesita internet (transformación y carga) en una copia temporal del repo.
Las etapas que consultan tiendas (precios, enlaces, venta en Colombia) usan sus archivos intermedios guardados.
"""
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
GENERADOS = ['data/fuentes_mvp/tonos_oficiales.csv', 'data/fuentes_mvp/tonos_color.csv',
             'etl/intermedios/equivalencias.csv', 'data/productos_mvp.csv']


def test_etl_regenera_el_catalogo_identico(tmp_path):
    shutil.copytree(RAIZ / 'etl', tmp_path / 'etl', ignore=shutil.ignore_patterns('__pycache__', 'fotos_productos'))
    shutil.copytree(RAIZ / 'data', tmp_path / 'data', ignore=shutil.ignore_patterns('fotos_paletas'))
    for f in GENERADOS:
        (tmp_path / f).unlink()

    for script in ('procesar_tonos_oficiales.py', 'procesar_tonos_color.py', 'importar_mi_base.py'):
        r = subprocess.run([sys.executable, f'etl/{script}'], cwd=tmp_path, capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, r.stderr

    for f in GENERADOS:
        assert (tmp_path / f).read_bytes() == (RAIZ / f).read_bytes(), f'{f} no coincide con el del repositorio'
