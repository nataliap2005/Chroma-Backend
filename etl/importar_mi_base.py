"""Arma el catálogo de Chroma (data/productos_mvp.csv). Todos los colores son oficiales de 5 marcas.

- Base y Corrector: tonos OFICIALES (nivel B) de data/fuentes_mvp/tonos_oficiales.csv
  (Vogue, Maybelline, L'Oréal Paris, Max Factor y Clinique). Precio de Falabella o Éxito cuando se verificó.
- Labial, Rubor, Bronzer, Iluminador y Sombras: tonos oficiales de las mismas marcas
  (data/fuentes_mvp/tonos_color.csv). Solo entran los productos con venta confirmada en Colombia
  (etl/intermedios/tiendas_color.json). En las paletas sin color publicado por sombra, el color se tomó
  de la foto oficial (columna origen_color = "foto").

Orden para regenerar:
  python etl/procesar_tonos_oficiales.py
  python etl/procesar_tonos_color.py
  python etl/tiendas_color.py
  python etl/importar_mi_base.py
  python scripts/export_catalog_sql.py   (genera el SQL para cargar el catálogo en Supabase)
"""
import csv
import json
import re
import statistics
from pathlib import Path

from rutas import CATALOGO, DATOS, INTERMEDIOS
OFICIALES = DATOS / 'tonos_oficiales.csv'
PRECIOS = INTERMEDIOS / 'precios_falabella.json'
COLOR = DATOS / 'tonos_color.csv'
TIENDAS_COLOR = INTERMEDIOS / 'tiendas_color.json'
IDS_COLOR = INTERMEDIOS / 'ids_color.json'   # id fijo por marca|producto|tono: al sumar productos no cambian los ids viejos
NUEVAS_2026_10_27 = {'Essence', 'Estée Lauder'}   # marcas agregadas después de la primera asignación de ids
SALIDA = CATALOGO

CAMPOS = ['id', 'nombre', 'marca', 'categoria', 'tono', 'profundidad', 'subtono', 'acabado', 'color_hex',
          'precio_cop', 'tipos_piel', 'estacion', 'descripcion', 'imagen', 'nivel', 'calidad', 'fuente',
          'precio_fuente', 'tienda', 'tienda_url', 'enlace_tipo', 'panes', 'origen_color']
SUB = {'cálido': 'calido', 'frío': 'frio', 'neutro': 'neutro'}
ACAB = {'mate': 'mate', 'natural': 'satinado', 'satinado': 'satinado', 'luminoso': 'luminoso', 'brillante': 'luminoso'}
ZONAS_TXT = 'claro: arco de la ceja y lagrimal; medio: párpado móvil; semioscuro: pliegue; oscuro: esquina externa'
PIEL = {'mate': 'normal;mixta;grasa', 'luminoso': 'normal;mixta;seca', 'satinado': 'normal;mixta;seca;grasa'}
# Precio estimado solo cuando no hay precio verificado en Falabella ni en Éxito
PRECIO_ESTIMADO = {'Vogue': 32000}
# Productos que solo aparecen en sitios de otros países y no se encontraron en tiendas colombianas:
# se dejan fuera del catálogo de la app para no recomendar algo que no se consigue.
SIN_VENTA_CO = {'Clinique|Beyond Perfecting Foundation + Concealer', 'Clinique|Daily Calm Makeup Balm',
                'Max Factor|Facefinity Compact', 'Max Factor|Smooth Effects', 'Max Factor|Healthy Skin Harmony',
                'Max Factor|Mastertouch Concealer'}
# Fotos tomadas de la página oficial colombiana cuando la tienda no tenía el producto
FOTOS_OFICIALES = {
    'Vogue|Base Polvo Resist': '/static/img/products/oficial/vogue-base-polvo-resist.jpg',
    'Vogue|Corrector Essential': '/static/img/products/oficial/vogue-corrector-essential.jpg',
    "L'Oréal Paris|True Match Eye Cream in a Concealer": '/static/img/products/oficial/loreal-paris-true-match-eye-cream-in-a-concealer.jpg',
    'Maybelline|Superstay Active Wear 30H Corrector': '/static/img/products/oficial/maybelline-superstay-active-wear-30h-corrector.jpg',
}


def estacion(sub, prof, C, color_producto):
    vivo = C >= (50 if color_producto else 38)
    suave = C < (35 if color_producto else 22)
    claro = prof == 'claro'
    profundo = prof in ('oscuro', 'profundo')
    if sub == 'calido':
        if profundo:
            return 'Otoño profundo' if prof == 'profundo' else ('Otoño suave' if suave else 'Otoño cálido')
        return 'Primavera clara' if claro and not vivo else ('Primavera brillante' if vivo else 'Primavera cálida')
    if sub == 'frio':
        if profundo:
            return 'Invierno profundo' if prof == 'profundo' else ('Invierno brillante' if vivo else 'Invierno frío')
        return 'Verano claro' if claro else ('Verano suave' if suave else 'Verano frío')
    return 'Otoño suave' if profundo else 'Verano suave'


def acabado_por_nombre(nombre):
    n = nombre.lower()
    if re.search(r'mat(e|te)|anti-blemish|pan stik|polvo|powder', n):
        return 'mate'
    if re.search(r'tint|serum|glow|luminous|illusion|balm|fresh|radiant|healthy', n):
        return 'luminoso'
    return 'satinado'


def limpio(t):
    return re.sub(r'\s+', ' ', re.sub(r'&trade;|&reg;|™|®', '', t)).strip()


def main():
    filas = []
    precios = json.load(open(PRECIOS, encoding='utf-8')) if PRECIOS.exists() else {}
    enlaces = json.load(open(INTERMEDIOS / 'enlaces_tono.json', encoding='utf-8')) if (INTERMEDIOS / 'enlaces_tono.json').exists() else {}
    por_marca = {}
    for k, v in precios.items():
        por_marca.setdefault(k.split('|')[0], []).append(v['precio_cop'])

    # 1) Bases y correctores oficiales (nivel B)
    with OFICIALES.open(encoding='utf-8') as f:
        for i, r in enumerate(csv.DictReader(f)):
            clave = f"{r['marca']}|{r['producto']}"
            if clave in SIN_VENTA_CO:
                continue
            p = precios.get(clave)
            if p:
                precio, foto = p['precio_cop'], p['imagen']
                fuente_precio = f"{p.get('fuente', 'Falabella Colombia')}, {p['fecha']}"
            elif r['marca'] in por_marca:
                precio, fuente_precio, foto = int(statistics.median(por_marca[r['marca']])), 'estimado (mediana de la marca en Falabella)', ''
            else:
                precio, fuente_precio, foto = PRECIO_ESTIMADO.get(r['marca'], 50000), 'estimado', ''
            foto = foto or FOTOS_OFICIALES.get(clave, '')
            # enlace de compra: del tono exacto si la tienda lo tiene; si no, del producto (se elige el tono allí)
            oferta = (enlaces.get(f"{clave}|{r['tono']}") or [None])[0]
            if oferta:
                tienda, tienda_url, enlace_tipo = oferta['tienda'], oferta['url'], 'tono'
                precio, fuente_precio = oferta['precio'], f"{oferta['tienda']} Colombia, precio de este tono"
            elif p and p.get('url'):
                tienda = 'Éxito' if 'exito' in p['url'] else 'Falabella'
                tienda_url, enlace_tipo = p['url'], 'producto'
            else:
                tienda, tienda_url, enlace_tipo = '', '', ''
            acab = acabado_por_nombre(r['producto'])
            filas.append({
                'id': f'CH-{5001 + i}', 'nombre': r['producto'], 'marca': r['marca'], 'categoria': r['categoria'],
                'tono': r['tono'], 'profundidad': r['profundidad'], 'subtono': r['subtono'], 'acabado': acab,
                'color_hex': r['hex'], 'precio_cop': precio, 'tipos_piel': PIEL[acab],
                'estacion': estacion(r['subtono'], r['profundidad'], float(r['C']), False),
                'descripcion': f"{r['categoria']} de {r['marca']}. Color oficial publicado por la marca; subtono {r['origen_subtono']}.",
                'imagen': foto, 'nivel': 'B', 'calidad': r['calidad'], 'fuente': r['fuente'],
                'precio_fuente': fuente_precio, 'tienda': tienda, 'tienda_url': tienda_url, 'enlace_tipo': enlace_tipo,
                'panes': '', 'origen_color': 'oficial'})

    # 2) Productos de color oficiales (nivel B) con venta confirmada en Colombia
    tiendas = json.load(open(TIENDAS_COLOR, encoding='utf-8')) if TIENDAS_COLOR.exists() else {}
    with COLOR.open(encoding='utf-8') as f:
        color = list(csv.DictReader(f))
    ids = json.load(open(IDS_COLOR, encoding='utf-8')) if IDS_COLOR.exists() else {}
    if not ids:   # primera asignación: el orden que tenía el catálogo antes de sumar marcas nuevas
        for i, r in enumerate(x for x in color if x['marca'] not in NUEVAS_2026_10_27):
            ids[f"{r['marca']}|{r['producto']}|{r['tono']}"] = f'CH-{7001 + i}'
    siguiente = max(int(v[3:]) for v in ids.values()) + 1 if ids else 7001
    for r in color:
        k = f"{r['marca']}|{r['producto']}|{r['tono']}"
        if k not in ids:
            ids[k], siguiente = f'CH-{siguiente}', siguiente + 1
    json.dump(ids, open(IDS_COLOR, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    for r in color:
        clave = f"{r['marca']}|{r['producto']}"
        t = tiendas.get(clave)
        if not t:
            continue                                   # sin venta confirmada en Colombia
        oferta = (t['tonos'].get(r['tono']) or [None])[0]
        if r['panes'] and not oferta and t['tonos']:
            continue                                   # paleta: solo las versiones vistas en tienda
        if oferta:
            precio, fuente_precio = oferta['precio'], f"{oferta['tienda']} Colombia, precio de este tono"
            tienda, tienda_url, enlace_tipo = oferta['tienda'], oferta['url'], 'tono'
        else:
            precio, fuente_precio = t['precio_cop'], f"{t['fuente']}, {t['fecha']}"
            tienda, tienda_url, enlace_tipo = t['tienda'], t['url'], 'producto'
        acab = ACAB[r['acabado']]
        if r['origen_color'] == 'foto':
            desc = (f"Paleta de {r['marca']}. La marca no publica el color de cada sombra: los colores se "
                    f"tomaron de la foto oficial del producto. Zonas ({ZONAS_TXT}).")
        elif r['panes']:
            desc = f"Paleta de {r['marca']}. Colores de cada sombra publicados por la marca. Zonas ({ZONAS_TXT})."
        else:
            desc = f"{r['categoria']} de {r['marca']}. Color oficial publicado por la marca; subtono calculado."
        if r['categoria_inferida']:
            desc += ' La categoría se dedujo del nombre del tono.'
        if r['calidad'] == 'transparente':
            desc += ' Tono transparente: no se compara por color.'
        filas.append({
            'id': ids[f"{r['marca']}|{r['producto']}|{r['tono']}"], 'nombre': r['producto'], 'marca': r['marca'], 'categoria': r['categoria'],
            'tono': r['tono'], 'profundidad': r['profundidad'], 'subtono': r['subtono'], 'acabado': acab,
            'color_hex': r['hex'], 'precio_cop': precio, 'tipos_piel': PIEL[acab],
            'estacion': estacion(r['subtono'], r['profundidad'], float(r['C']), True),
            'descripcion': desc, 'imagen': r['imagen_paleta'] or t['imagen'], 'nivel': 'B',
            'calidad': r['calidad'], 'fuente': r['fuente'], 'precio_fuente': fuente_precio, 'tienda': tienda,
            'tienda_url': tienda_url, 'enlace_tipo': enlace_tipo, 'panes': r['panes'],
            'origen_color': r['origen_color']})

    with SALIDA.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS, extrasaction='ignore', lineterminator='\n')
        w.writeheader()
        w.writerows(filas)
    from collections import Counter
    print(f'{len(filas)} productos -> {SALIDA.name}')
    print(dict(Counter((r["categoria"], r["nivel"]) for r in filas)))


if __name__ == '__main__':
    main()
