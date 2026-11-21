"""Completa precio y foto desde Éxito (API pública de catálogo) para los productos sin precio verificado.

Para cada producto pendiente busca en Éxito, conserva solo los resultados de la misma marca que
contienen TODAS las palabras clave del producto y ninguna palabra excluida, y guarda la mediana del
precio de sus tonos y la foto del primero. Si no hay resultados, el producto queda marcado como
"sin venta confirmada en Colombia".

Salida: actualiza etl/intermedios/precios_falabella.json (mismo formato; campo `fuente` indica la tienda)
        fotos en etl/fotos_productos/

Uso:  python etl/precios_exito.py
"""
import json
import re
import statistics
import subprocess
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import quote

from rutas import FOTOS, INTERMEDIOS
PRECIOS = INTERMEDIOS / 'precios_falabella.json'
EXCLUIR_SIEMPRE = ['unas', 'unias', 'procrecimiento', 'fortalecimiento', 'labial', 'pestan', 'sombra', 'esmalte', 'gafas']

# producto -> (búsqueda, palabras obligatorias, palabras excluidas)
PENDIENTES = {
    'Vogue|Base Líquida Resist': ('vogue base resist', ['base', 'resist'], ['glam', 'polvo', 'corrector']),
    'Vogue|Base Líquida Mate Natural': ('vogue base mate natural', ['base', 'mate natural'], ['corrector', 'polvo']),
    'Vogue|Base Resist Glam': ('vogue resist glam', ['glam'], ['corrector', 'polvo']),
    'Vogue|Base Líquida Essential': ('vogue base essential', ['base', 'essential'], ['corrector', 'polvo']),
    'Vogue|Base Polvo Resist': ('vogue polvo resist', ['polvo', 'resist'], ['corrector']),
    'Vogue|Corrector Líquido Resist': ('vogue corrector resist', ['corrector', 'resist'], []),
    'Vogue|Corrector Líquido Mate Natural': ('vogue corrector matte natural', ['corrector', 'matte natural'], []),
    'Vogue|Corrector Essential': ('vogue corrector essential', ['corrector', 'essential'], []),
    'Clinique|Beyond Perfecting Foundation + Concealer': ('clinique beyond perfecting', ['beyond'], ['polvo', 'powder']),
    'Clinique|Daily Calm Makeup Balm': ('clinique daily calm', ['daily calm'], ['crema', 'cream']),
    "L'Oréal Paris|True Match Base de Maquillaje": ('loreal true match base', ['true match'], ['serum', 'tinted', 'corrector', 'polvo']),
    "L'Oréal Paris|True Match Eye Cream in a Concealer": ('loreal true match corrector', ['true match', 'corrector'], []),
    'Max Factor|Facefinity Compact': ('max factor facefinity compact', ['facefinity', 'compact'], []),
    'Max Factor|Smooth Effects': ('max factor smooth effects', ['smooth'], []),
    'Max Factor|Healthy Skin Harmony': ('max factor healthy skin', ['healthy skin'], []),
    'Max Factor|Mastertouch Concealer': ('max factor mastertouch', ['mastertouch'], []),
    'Maybelline|Superstay Active Wear 30H Corrector': ('maybelline superstay corrector 30h', ['corrector', 'superstay'], []),
}


def norm(t):
    t = unicodedata.normalize('NFD', t.lower())
    t = ''.join(c for c in t if unicodedata.category(c) != 'Mn').replace("'", '')
    return re.sub(r'\s+', ' ', re.sub(r'super stay', 'superstay', re.sub(r'[^a-z0-9 ]+', ' ', t))).strip()


def curl(url):
    r = subprocess.run(['curl', '-sL', '-m', '30', '-A', 'Mozilla/5.0', url], capture_output=True)
    return r.stdout


def buscar(texto):
    try:
        datos = json.loads(curl('https://www.exito.com/api/catalog_system/pub/products/search?ft='
                                + quote(texto) + '&_from=0&_to=29'))
    except ValueError:
        return []
    out = []
    for p in datos if isinstance(datos, list) else []:
        for it in p.get('items', []):
            oferta = it['sellers'][0]['commertialOffer'] if it.get('sellers') else {}
            out.append(dict(marca=p.get('brand', ''), nombre=p.get('productName', ''), url=p.get('link', ''),
                            precio=oferta.get('Price') or 0, imagen=(it.get('images') or [{}])[0].get('imageUrl', '')))
    return out


def main():
    FOTOS.mkdir(parents=True, exist_ok=True)
    precios = json.load(open(PRECIOS, encoding='utf-8'))
    for clave, (q, oblig, excl) in PENDIENTES.items():
        if clave in precios:
            continue
        marca = norm(clave.split('|')[0]).replace(' paris', '')
        candidatos = []
        for r in buscar(q):
            texto = norm(r['nombre'] + ' ' + r['marca'])
            if marca.replace(' ', '') not in texto.replace(' ', '') or r['precio'] <= 0:
                continue
            if all(norm(w) in texto for w in oblig) and not any(norm(w) in texto for w in excl + EXCLUIR_SIEMPRE):
                candidatos.append(r)
        if not candidatos:
            print(f'  sin venta confirmada: {clave}')
            continue
        precio = int(statistics.median(c['precio'] for c in candidatos))
        archivo = re.sub(r'\s+', '-', norm(clave.replace('|', ' '))) + '.jpg'
        img = curl(candidatos[0]['imagen'].split('?')[0])
        if len(img) > 2000:
            (FOTOS / archivo).write_bytes(img)
        precios[clave] = dict(precio_cop=precio, nombre_falabella=candidatos[0]['nombre'], url=candidatos[0]['url'],
                              imagen=f'/static/img/products/oficial/{archivo}' if len(img) > 2000 else '',
                              coincidencia=1.0, fecha=str(date.today()),
                              fuente=f'Éxito Colombia (mediana de {len(candidatos)} tonos)')
        print(f'  ok  {clave}  ←  {candidatos[0]["nombre"][:55]}  ${precio:,}  ({len(candidatos)} tonos)')
    json.dump(precios, open(PRECIOS, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'{len(precios)} productos con precio verificado')


if __name__ == '__main__':
    main()
