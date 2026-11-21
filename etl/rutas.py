"""Rutas compartidas por los scripts del ETL del catálogo."""
from pathlib import Path

ETL = Path(__file__).resolve().parent
RAIZ = ETL.parent
DATOS = RAIZ / 'data' / 'fuentes_mvp'              # tonos_oficiales.csv y tonos_color.csv (procesados)
FUENTES_OFICIALES = DATOS / 'fuentes_oficiales'      # colores tal como los publica cada marca (extracción)
INTERMEDIOS = ETL / 'intermedios'                    # precios, enlaces, tiendas, ids fijos y equivalencias
FOTOS = ETL / 'fotos_productos'                      # fotos descargadas de las tiendas (no se suben a Git)
CATALOGO = RAIZ / 'data' / 'productos_mvp.csv'      # catálogo final que usa la API
