"""Busca precio en pesos y foto de cada producto oficial en Falabella Colombia.

Lee los productos de data/fuentes_mvp/fuentes_oficiales/*.json, busca "marca + producto" en Falabella,
elige el resultado de la misma marca con más palabras en común y guarda:
  etl/intermedios/precios_falabella.json   {marca|producto: {precio_cop, nombre_falabella, url, imagen, fecha}}
  etl/fotos_productos/*.jpg  (una foto por producto)

Uso:  python etl/precios_falabella.py
"""
import html
import json
import re
import subprocess
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import quote

from rutas import FOTOS, FUENTES_OFICIALES, INTERMEDIOS
SALIDA = INTERMEDIOS / 'precios_falabella.json'
UA = 'Mozilla/5.0'

# Búsquedas ajustadas para nombres poco comunes
BUSQUEDA = {
    'Vogue|Base Líquida Resist': 'Vogue base liquida resist',
    'Vogue|Base Líquida Mate Natural': 'Vogue base mate natural',
    'Vogue|Base Resist Glam': 'Vogue base resist glam',
    'Vogue|Base Líquida Essential': 'Vogue base essential',
    'Vogue|Base Polvo Resist': 'Vogue polvo resist',
    'Vogue|Corrector Líquido Resist': 'Vogue corrector resist',
    'Vogue|Corrector Líquido Mate Natural': 'Vogue corrector mate natural',
    'Vogue|Corrector Essential': 'Vogue corrector essential',
    "L'Oréal Paris|True Match Base de Maquillaje": 'Loreal true match base',
    "L'Oréal Paris|Infallible More Than a Concealer": 'Loreal infallible corrector',
    "L'Oréal Paris|True Match Eye Cream in a Concealer": 'Loreal true match corrector',
    'Max Factor|Facefinity All Day Flawless 3 in 1': 'Max Factor facefinity base',
    'Clinique|Even Better Makeup SPF 15': 'Clinique even better makeup',
    'Clinique|Even Better Clinical Serum Foundation SPF 20': 'Clinique even better clinical',
    'Clinique|Beyond Perfecting Foundation + Concealer': 'Clinique beyond perfecting',
    'Clinique|Anti-Blemish Solutions Liquid Makeup': 'Clinique anti blemish base',
    'Clinique|Daily Calm Makeup Balm': 'Clinique daily calm',
    'Clinique|Even Better Concealer': 'Clinique even better corrector',
}


def norm(t):
    t = unicodedata.normalize('NFD', t.lower())
    return re.sub(r'[^a-z0-9 ]+', ' ', ''.join(c for c in t if unicodedata.category(c) != 'Mn').replace("'", ''))


def curl(url):
    r = subprocess.run(['curl', '-sfL', '-m', '30', '-A', UA, url], capture_output=True)
    return r.stdout if r.returncode == 0 else b''


def buscar(texto):
    pagina = curl('https://www.falabella.com.co/falabella-co/search?Ntt=' + quote(texto))
    out = []
    for bloque in re.findall(rb'<script type="application/ld\+json">(.*?)</script>', pagina, re.S):
        try:
            data = json.loads(html.unescape(bloque.decode('utf-8', 'ignore')))
        except ValueError:
            continue
        for it in data.get('itemListElement', []) if isinstance(data, dict) else []:
            p = it.get('item', {}) if isinstance(it, dict) else {}
            if not isinstance(p, dict) or not isinstance(p.get('image'), str):
                continue
            ofertas = p.get('offers') or []
            precio = ofertas[0].get('price') if ofertas and isinstance(ofertas[0], dict) else None
            out.append(dict(nombre=p.get('name', ''), marca=(p.get('brand') or {}).get('name', ''),
                            url=p.get('url', ''), imagen=p['image'], precio=precio))
    return out


def mejor(resultados, marca, producto):
    m = norm(marca).replace(' ', '').replace('paris', '')
    palabras = [w for w in norm(producto).split() if len(w) > 2 and w not in ('base', 'de', 'maquillaje', 'spf')]
    elegido, puntaje = None, 0
    for r in resultados:
        texto = norm(r['nombre'] + ' ' + r['marca'])
        if m not in texto.replace(' ', '') or not r['precio']:
            continue
        s = sum(w in texto for w in palabras) / max(1, len(palabras)) + 0.01
        if s > puntaje:
            elegido, puntaje = r, s
    return elegido, puntaje


def main():
    FOTOS.mkdir(parents=True, exist_ok=True)
    salida = {}
    for f in sorted((FUENTES_OFICIALES).glob('*.json')):
        d = json.load(open(f, encoding='utf-8'))
        for p in d['productos']:
            clave = f"{d['marca']}|{p['nombre']}"
            r, s = mejor(buscar(BUSQUEDA.get(clave, f"{d['marca']} {p['nombre']}")), d['marca'], p['nombre'])
            if not r:
                print(f'  sin resultado: {clave}')
                continue
            archivo = re.sub(r'\s+', '-', norm(clave.replace('|', ' ')).strip()) + '.jpg'
            img = curl(re.sub(r'/public$', '', r['imagen']) + '/width=480,height=480,quality=80,format=jpg,fit=pad')
            if len(img) > 2000:
                (FOTOS / archivo).write_bytes(img)
            salida[clave] = dict(precio_cop=int(float(r['precio'])), nombre_falabella=r['nombre'], url=r['url'],
                                 imagen=f'/static/img/products/oficial/{archivo}' if len(img) > 2000 else '',
                                 coincidencia=round(s, 2), fecha=str(date.today()))
            print(f"  {s:.2f}  {clave}  ←  {r['nombre'][:60]}  ${int(float(r['precio'])):,}")
    json.dump(salida, open(SALIDA, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'{len(salida)} productos con precio')


if __name__ == '__main__':
    main()
