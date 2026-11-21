"""Procesa los productos de color (labial, rubor, bronzer, iluminador y sombras) de las 5 marcas.

Entrada:  data/fuentes_mvp/fuentes_oficiales/color_*.jsonl   (una línea por producto, extraída de la página oficial)
Salida:   data/fuentes_mvp/tonos_color.csv                   (un tono o una paleta por fila)

Origen del color (columna `origen_color`)
-----------------------------------------
- "oficial": color publicado por la marca en el selector de tonos de su página (nivel B).
- "foto":    paletas cuyo sitio no publica el color de cada sombra; el color se tomó de la foto
             oficial del producto (mediana de los píxeles del centro de cada sombra).

Reglas
------
1. Subtono de un color de maquillaje (no de piel), por el ángulo de tono h en CIELAB:
   h < 25° o h > 300° → frío (rosados, fucsias, malvas, rojos azulados)
   25° ≤ h ≤ 40°       → neutro (rojos verdaderos; el rojo puro está cerca de 40°)
   h > 40°             → cálido (corales, durazno, terracota, marrones)
   Colores casi grises (croma < 8) → neutro.
2. Calidad:
   - "ambiguo":      dos tonos del mismo producto con el mismo color exacto, o la página publica
                     dos colores distintos con el mismo nombre.
   - "transparente": labial o brillo casi blanco y sin color (p. ej. "Clear"); no se compara por color.
   - "ok".
3. Sombras: cada sombra de una paleta se ubica en una zona del ojo según su claridad
   (claro → arco de la ceja y lagrimal; medio → párpado móvil; semioscuro → pliegue;
   oscuro → esquina externa). El subtono de la paleta es el de la mayoría de sus sombras.

Uso:  python etl/procesar_tonos_color.py
"""
import csv
import json
import math
from collections import Counter
from pathlib import Path

from procesar_tonos_oficiales import hex_a_lab

from rutas import DATOS, FUENTES_OFICIALES
FUENTES = FUENTES_OFICIALES
FECHA = '2026-10-27'
ZONAS = {'claro': 'Arco de la ceja y lagrimal', 'medio': 'Párpado móvil',
         'semioscuro': 'Pliegue del párpado', 'oscuro': 'Esquina externa'}


def lab(hx):
    L, a, b = hex_a_lab(hx)
    return L, a, b, math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360


def subtono_color(hx):
    _, _, _, C, h = lab(hx)
    if C < 8:
        return 'neutro'
    if h < 25 or h > 300:
        return 'frio'
    return 'neutro' if h <= 40 else 'calido'


def profundidad_color(L):
    return 'claro' if L >= 60 else 'medio' if L >= 45 else 'oscuro' if L >= 32 else 'profundo'


def zona(L):
    return 'claro' if L >= 75 else 'medio' if L >= 60 else 'semioscuro' if L >= 45 else 'oscuro'


def transparente(categoria, nombre, hx):
    L, _, _, C, _ = lab(hx)
    return categoria == 'Labial' and (L > 88 and C < 10 or nombre.lower() in ('clear', 'cristal clear', 'clear crave'))


def productos():
    for f in sorted(FUENTES.glob('color_*.jsonl')):
        for linea in f.read_text(encoding='utf-8').splitlines():
            if linea.strip():
                yield json.loads(linea)


def main():
    filas = []
    for p in productos():
        dudosos = p.get('dudosos', {})
        comun = dict(marca=p['marca'], producto=p['nombre'], fuente=p['url'], fecha=FECHA, nivel='B')
        for t in p.get('tonos', []):
            nombre, hx = t[0], t[1].upper()
            categoria = t[2] if len(t) > 2 and t[2] else p['categoria']
            L, a, b, C, h = lab(hx)
            repetido = sum(1 for x in p['tonos'] if x[1].upper() == hx) > 1
            calidad = ('transparente' if transparente(categoria, nombre, hx)
                       else 'ambiguo' if repetido or nombre in dudosos else 'ok')
            filas.append(dict(comun, categoria=categoria, tono=nombre, hex=hx, L=round(L, 2), a=round(a, 2),
                              b=round(b, 2), C=round(C, 2), h=round(h, 2), profundidad=profundidad_color(L),
                              subtono=subtono_color(hx), calidad=calidad,
                              acabado=p.get('acabado_tono', {}).get(nombre, p['acabado']),
                              origen_color='oficial', panes='',
                              categoria_inferida='sí' if len(t) > 2 and t[2] else ''))
        for pal in p.get('paletas', []):
            panes = []
            for nombre, hx in pal['panes']:
                L, *_ = lab(hx)
                z = zona(L)
                panes.append(dict(nombre=nombre, hex=hx.upper(), zona=z, lugar=ZONAS[z], subtono=subtono_color(hx)))
            votos = Counter(x['subtono'] for x in panes).most_common()
            sub = votos[0][0] if len(votos) == 1 or votos[0][1] > votos[1][1] else 'neutro'
            # color representativo: la sombra para el párpado móvil (o la de claridad intermedia)
            orden = sorted(panes, key=lambda x: lab(x['hex'])[0])
            rep = next((x for x in panes if x['zona'] == 'medio'), orden[len(orden) // 2])
            L, a, b, C, h = lab(rep['hex'])
            filas.append(dict(comun, categoria='Sombras', tono=pal['nombre'], hex=rep['hex'], L=round(L, 2),
                              a=round(a, 2), b=round(b, 2), C=round(C, 2), h=round(h, 2),
                              profundidad=profundidad_color(L), subtono=sub, calidad='ok', acabado=p['acabado'],
                              origen_color=pal['origen'], panes=json.dumps(panes, ensure_ascii=False),
                              imagen_paleta=pal.get('imagen', ''), categoria_inferida=''))
    for i, r in enumerate(filas):
        r['id'] = f'CO-{i + 1:04d}'
    campos = ['id', 'marca', 'categoria', 'producto', 'tono', 'hex', 'L', 'a', 'b', 'C', 'h', 'profundidad', 'subtono',
              'calidad', 'acabado', 'origen_color', 'panes', 'imagen_paleta', 'categoria_inferida', 'nivel', 'fuente', 'fecha']
    with open(DATOS / 'tonos_color.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=campos, extrasaction='ignore')
        w.writeheader()
        w.writerows(filas)
    print(f'{len(filas)} filas -> tonos_color.csv')
    print('por categoría:', dict(Counter(r['categoria'] for r in filas)))
    print('calidad:', dict(Counter(r['calidad'] for r in filas)))
    print('origen del color:', dict(Counter(r['origen_color'] for r in filas)))
    print('subtono:', dict(Counter(r['subtono'] for r in filas)))


if __name__ == '__main__':
    main()
