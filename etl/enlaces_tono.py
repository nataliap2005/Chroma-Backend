"""Enlaza cada TONO oficial con su página de compra en tiendas colombianas (Éxito y Falabella).

Para cada producto busca en las dos tiendas y empareja tono por tono:
- Éxito (API pública de catálogo): cada variante (SKU) trae el nombre del tono, precio y disponibilidad.
- Falabella (resultados de búsqueda): cada resultado suele ser un tono.
Un resultado se acepta solo si: es de la misma marca, contiene las palabras clave del producto,
su enlace corresponde a la marca o al producto (descarta listados mal etiquetados) y contiene el
nombre o código del tono.

Salida: etl/intermedios/enlaces_tono.json   {"marca|producto|tono": [{tienda, url, precio, disponible, nombre}]}
Uso:    python etl/enlaces_tono.py
"""
import csv
import html
import json
import re
import subprocess
import unicodedata
from pathlib import Path
from urllib.parse import quote

from rutas import DATOS, INTERMEDIOS
SALIDA = INTERMEDIOS / 'enlaces_tono.json'

# producto -> (búsqueda, palabras clave que debe tener el nombre en la tienda)
PRODUCTOS = {
    'Vogue|Base Líquida Resist': ('vogue base resist', ['resist']),
    'Vogue|Base Líquida Mate Natural': ('vogue base mate natural', ['mat', 'natural']),
    'Vogue|Base Resist Glam': ('vogue resist glam', ['glam']),
    'Vogue|Base Líquida Essential': ('vogue base essential', ['essential']),
    'Vogue|Base Polvo Resist': ('vogue polvo resist', ['polvo', 'resist']),
    'Vogue|Corrector Líquido Resist': ('vogue corrector resist', ['corrector', 'resist']),
    'Vogue|Corrector Líquido Mate Natural': ('vogue corrector matte natural', ['corrector', 'mat']),
    'Vogue|Corrector Essential': ('vogue corrector essential', ['corrector', 'essential']),
    'Maybelline|Fit Me Fresh Tint SPF50': ('maybelline fit me fresh tint', ['fresh tint']),
    'Maybelline|Super Stay Active Wear': ('maybelline superstay active wear base', ['superstay', 'base']),
    'Maybelline|Superstay Lumi-Matte': ('maybelline superstay lumi matte', ['lumi']),
    'Maybelline|Fit Me Matte + Poreless': ('maybelline fit me matte poreless', ['fit me', 'base']),
    'Maybelline|Instant Age Rewind Eraser': ('maybelline instant age rewind', ['age rewind']),
    'Maybelline|Superstay Active Wear 30H Corrector': ('maybelline superstay corrector', ['superstay', 'corrector']),
    "L'Oréal Paris|True Match Tinted Serum": ('loreal true match tinted serum', ['tinted']),
    "L'Oréal Paris|True Match Base de Maquillaje": ('loreal true match base', ['true match']),
    "L'Oréal Paris|Infallible 24H Fresh Wear": ('loreal infallible fresh wear base', ['fresh wear', 'base']),
    "L'Oréal Paris|Infallible 24H Pro Matte": ('loreal infallible pro matte', ['pro matte']),
    "L'Oréal Paris|Infallible More Than a Concealer": ('loreal infallible concealer', ['concealer']),
    "L'Oréal Paris|True Match Eye Cream in a Concealer": ('loreal true match concealer', ['true match', 'concealer']),
    'Max Factor|Facefinity All Day Flawless 3 in 1': ('max factor facefinity base', ['facefinity', 'base']),
    'Max Factor|Lasting Performance': ('max factor lasting performance', ['lasting']),
    'Max Factor|Miracle Touch Liquid Illusion': ('max factor miracle touch', ['miracle']),
    'Max Factor|Pan Stik': ('max factor pan stik', ['pan stik']),
    'Clinique|Even Better Makeup SPF 15': ('clinique even better makeup spf 15', ['even better', '15']),
    'Clinique|Even Better Clinical Serum Foundation SPF 20': ('clinique even better clinical serum', ['clinical']),
    'Clinique|Anti-Blemish Solutions Liquid Makeup': ('clinique anti blemish', ['blemish']),
    'Clinique|Even Better Concealer': ('clinique even better concealer', ['even better', 'concealer']),
}
GENERICAS = {'tono', 'base', 'the', 'and', 'con', 'maquillaje', 'liquida', 'ml'}


def norm(t):
    t = unicodedata.normalize('NFD', (t or '').lower())
    t = ''.join(c for c in t if unicodedata.category(c) != 'Mn').replace("'", '')
    t = re.sub(r'super stay', 'superstay', t)
    return ' ' + re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9.]+', ' ', t)).strip() + ' '


def curl(url):
    return subprocess.run(['curl', '-sL', '-m', '30', '-A', 'Mozilla/5.0', url], capture_output=True).stdout


def vtex(host, tienda, q):
    """Tiendas con la API pública de catálogo VTEX (Éxito, Jumbo, Locatel)."""
    try:
        datos = json.loads(curl(f'https://{host}/api/catalog_system/pub/products/search?ft='
                                + quote(q) + '&_from=0&_to=49'))
    except ValueError:
        return []
    out = []
    for p in datos if isinstance(datos, list) else []:
        for it in p.get('items', []):
            o = it['sellers'][0]['commertialOffer'] if it.get('sellers') else {}
            out.append(dict(tienda=tienda, marca=p.get('brand', ''), producto=p.get('productName', ''),
                            variante=f"{it.get('name', '')} {it.get('nameComplete', '')}", url=p.get('link', ''),
                            precio=int(o.get('Price') or 0), disponible=(o.get('AvailableQuantity') or 0) > 0,
                            imagen=(it.get('images') or [{}])[0].get('imageUrl', '')))
    return out


def exito(q):
    return vtex('www.exito.com', 'Éxito', q)


def jumbo(q):
    return vtex('www.tiendasjumbo.co', 'Jumbo', q)


def locatel(q):
    return vtex('www.locatelcolombia.com', 'Locatel', q)


def falabella(q):
    pagina = curl('https://www.falabella.com.co/falabella-co/search?Ntt=' + quote(q))
    out = []
    for bloque in re.findall(rb'<script type="application/ld\+json">(.*?)</script>', pagina, re.S):
        try:
            data = json.loads(html.unescape(bloque.decode('utf-8', 'ignore')))
        except ValueError:
            continue
        for it in data.get('itemListElement', []) if isinstance(data, dict) else []:
            p = it.get('item', {}) if isinstance(it, dict) else {}
            if not isinstance(p, dict) or not p.get('url'):
                continue
            of = p.get('offers') or []
            precio = of[0].get('price') if of and isinstance(of[0], dict) else 0
            out.append(dict(tienda='Falabella', marca=(p.get('brand') or {}).get('name', ''), producto=p.get('name', ''),
                            variante=p.get('name', ''), url=p['url'], precio=int(float(precio or 0)), disponible=True,
                            imagen=(p.get('image') if isinstance(p.get('image'), str) else (p.get('image') or [''])[0])))
    return out


def tokens_tono(tono):
    t = norm(tono)
    palabras = [w for w in t.split() if w.isalpha() and len(w) >= 3 and w not in GENERICAS]
    numeros = [w for w in t.split() if re.fullmatch(r'\d+(\.\d+)?', w)]
    return palabras, numeros


def coincide_tono(texto, tono):
    palabras, numeros = tokens_tono(tono)
    if palabras:
        return all(f' {w} ' in texto for w in palabras)
    return bool(numeros) and all(f' {n} ' in texto for n in numeros)


def main():
    tonos, categoria = {}, {}
    with open(DATOS / 'tonos_oficiales.csv', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            tonos.setdefault(f"{r['marca']}|{r['producto']}", []).append(r['tono'])
            categoria[f"{r['marca']}|{r['producto']}"] = r['categoria']
    salida, resumen = {}, []
    for clave, (q, claves) in PRODUCTOS.items():
        marca = norm(clave.split('|')[0]).replace(' paris ', ' ').strip().replace(' ', '')
        resultados = exito(q) + falabella(q)
        validos = []
        for r in resultados:
            texto = norm(r['producto'] + ' ' + r['variante'] + ' ' + r['marca'])
            slug = norm(r['url'].replace('-', ' ').replace('/', ' '))
            if marca not in texto.replace(' ', '') or r['precio'] <= 0:
                continue
            if not all(norm(k).strip() in texto for k in claves):
                continue
            # misma categoría: una base no se enlaza a un corrector ni a un polvo con el mismo nombre de tono
            if categoria.get(clave) == 'Base' and (' corrector ' in texto or ' concealer ' in texto):
                continue
            if ' polvo ' in texto and 'polvo' not in norm(clave):
                continue
            if marca not in slug.replace(' ', '') and not any(norm(k).strip() in slug for k in claves):
                continue                                   # listado mal etiquetado (enlace a otro producto)
            validos.append((texto, r))
        enlazados = 0
        for tono in tonos.get(clave, []):
            ofertas = [dict(tienda=r['tienda'], url=r['url'], precio=r['precio'], disponible=r['disponible'],
                            nombre=(r['producto'] + ' · ' + r['variante'].split(' ' + r['producto'][:10])[0]).strip()[:120])
                       for texto, r in validos if coincide_tono(texto, tono)]
            vistos, unicas = set(), []
            for o in sorted(ofertas, key=lambda o: (not o['disponible'], o['precio'])):
                if o['url'] not in vistos:
                    vistos.add(o['url'])
                    unicas.append(o)
            if unicas:
                salida[f'{clave}|{tono}'] = unicas[:3]
                enlazados += 1
        resumen.append((clave, enlazados, len(tonos.get(clave, []))))
        print(f'  {enlazados:>2}/{len(tonos.get(clave, [])):<2} tonos con enlace  ·  {clave}')
    json.dump(salida, open(SALIDA, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    total = sum(t for _, _, t in resumen)
    print(f'{len(salida)} de {total} tonos con enlace directo a tienda')


if __name__ == '__main__':
    main()
