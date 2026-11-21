"""Procesa los tonos oficiales (nivel B) de las 5 marcas y calcula equivalencias confiables.

Entrada:  data/fuentes_mvp/fuentes_oficiales/*.json  (un archivo por marca, extraído de su página oficial)
Salida:   data/fuentes_mvp/tonos_oficiales.csv       (un tono por fila, con su color, subtono y control de calidad)
          etl/intermedios/equivalencias.csv         (pares de tonos equivalentes entre marcas)

Reglas de confiabilidad
-----------------------
1. Solo se usan colores publicados por la marca (nivel B).
2. Subtono: si la marca lo declara en el código del tono (Clinique WN/CN, True Match N/W/D),
   se usa ese; si no, se calcula con el ángulo de tono (h) comparando con tonos de claridad parecida.
3. Control de calidad (columna `calidad`):
   - "ambiguo":     dos tonos distintos del mismo producto con el mismo color exacto.
   - "incoherente": el nombre indica un tono profundo pero el color es muy claro (o al revés).
   - "ok":          ninguno de los anteriores.
   Solo los tonos "ok" entran a las equivalencias.
4. Equivalencia: misma categoría, marca distinta, mismo subtono y ΔE00 <= 3.

Uso:  python etl/procesar_tonos_oficiales.py
"""
import csv
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

from rutas import DATOS, FUENTES_OFICIALES, INTERMEDIOS
FUENTES = FUENTES_OFICIALES
MAX_DE = 3.0

PROFUNDO = re.compile(r'deep|dark|tan\b|bronze|caramel|mocha|java|toffee|cocoa|espresso|sable|tawny|copper|canela|bronce|caramelo|cafe|café|miel|honey|chocolate|nuez', re.I)
CLARO = re.compile(r'fair|porcelain|porcelana|ivory|alabaster|light\b|vanilla|vainilla|crema|linen|bone|breeze|marfil|pearl', re.I)


def hex_a_lab(h):
    h = h.lstrip('#')
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    lin = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = lin(r), lin(g), lin(b)
    x = (r * 0.4124 + g * 0.3576 + b * 0.1805) / 0.95047
    y = r * 0.2126 + g * 0.7152 + b * 0.0722
    z = (r * 0.0193 + g * 0.1192 + b * 0.9505) / 1.08883
    f = lambda t: t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    return 116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))


def de2000(p, q):
    L1, a1, b1 = p
    L2, a2, b2 = q
    rad = math.pi / 180
    C1, C2 = math.hypot(a1, b1), math.hypot(a2, b2)
    Cm = (C1 + C2) / 2
    G = 0.5 * (1 - math.sqrt(Cm ** 7 / (Cm ** 7 + 25 ** 7)))
    a1p, a2p = a1 * (1 + G), a2 * (1 + G)
    C1p, C2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360
    h2p = math.degrees(math.atan2(b2, a2p)) % 360
    dLp, dCp = L2 - L1, C2p - C1p
    dhp = 0
    if C1p * C2p:
        dhp = h2p - h1p
        dhp -= 360 if dhp > 180 else 0
        dhp += 360 if dhp < -180 else 0
    dHp = 2 * math.sqrt(C1p * C2p) * math.sin(dhp * rad / 2)
    Lpm, Cpm = (L1 + L2) / 2, (C1p + C2p) / 2
    hpm = h1p + h2p
    if C1p * C2p:
        hpm = (h1p + h2p + (360 if h1p + h2p < 360 else -360)) / 2 if abs(h1p - h2p) > 180 else (h1p + h2p) / 2
    T = (1 - 0.17 * math.cos((hpm - 30) * rad) + 0.24 * math.cos(2 * hpm * rad)
         + 0.32 * math.cos((3 * hpm + 6) * rad) - 0.2 * math.cos((4 * hpm - 63) * rad))
    dth = 30 * math.exp(-(((hpm - 275) / 25) ** 2))
    Rc = 2 * math.sqrt(Cpm ** 7 / (Cpm ** 7 + 25 ** 7))
    Sl = 1 + 0.015 * (Lpm - 50) ** 2 / math.sqrt(20 + (Lpm - 50) ** 2)
    Sc, Sh = 1 + 0.045 * Cpm, 1 + 0.015 * Cpm * T
    Rt = -math.sin(2 * dth * rad) * Rc
    return math.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2 + Rt * (dCp / Sc) * (dHp / Sh))


def subtono_declarado(marca, tono):
    t = tono.upper()
    if marca == 'Clinique':
        m = re.match(r'(WW|WN|CN|CW|C|W|N)\s*\d', t)
        if m:
            return {'W': 'calido', 'C': 'frio', 'N': 'neutro'}[m.group(1)[0]]
    if marca == "L'Oréal Paris":
        m = re.search(r'\b\d(?:\.\d)?\.?([NWDRC])\b|\b([NWDRC])\d', t)
        if m:
            letra = m.group(1) or m.group(2)
            return {'N': 'neutro', 'W': 'calido', 'D': 'calido', 'R': 'frio', 'C': 'frio'}[letra]
    return None


def profundidad(L):
    return 'claro' if L >= 72 else 'medio' if L >= 58 else 'oscuro' if L >= 42 else 'profundo'


def main():
    filas = []
    for f in sorted(FUENTES.glob('*.json')):
        d = json.load(open(f, encoding='utf-8'))
        for p in d['productos']:
            colores = Counter(h.upper() for _, h in p['tonos'])
            for tono, hx in p['tonos']:
                L, a, b = hex_a_lab(hx)
                filas.append(dict(marca=d['marca'], categoria=p['categoria'], producto=p['nombre'], tono=tono.strip(),
                                  hex=hx.upper(), L=round(L, 2), a=round(a, 2), b=round(b, 2),
                                  C=round(math.hypot(a, b), 2), h=round(math.degrees(math.atan2(b, a)) % 360, 2),
                                  subtono_declarado=subtono_declarado(d['marca'], tono) or '',
                                  duplicado=colores[hx.upper()] > 1,
                                  fuente=d['sitio'] + p['url'], fecha=d['fecha'], nivel=d['nivel']))
    # subtono calculado: dentro de cada franja de claridad, h alto = más amarillo (cálido)
    franjas = defaultdict(list)
    for r in filas:
        franjas[profundidad(r['L'])].append(r['h'])
    cortes = {}
    for k, hs in franjas.items():
        hs = sorted(hs)
        cortes[k] = (hs[len(hs) // 3], hs[2 * len(hs) // 3])
    for r in filas:
        r['profundidad'] = profundidad(r['L'])
        lo, hi = cortes[r['profundidad']]
        calculado = 'frio' if r['h'] < lo else 'calido' if r['h'] > hi else 'neutro'
        r['subtono'] = r['subtono_declarado'] or calculado
        r['origen_subtono'] = 'declarado por la marca' if r['subtono_declarado'] else 'calculado (ángulo de tono)'
        if r['duplicado']:
            r['calidad'] = 'ambiguo'
        elif PROFUNDO.search(r['tono']) and not CLARO.search(r['tono']) and r['L'] > 74:
            r['calidad'] = 'incoherente'
        elif CLARO.search(r['tono']) and not PROFUNDO.search(r['tono']) and r['L'] < 58:
            r['calidad'] = 'incoherente'
        else:
            r['calidad'] = 'ok'
    for i, r in enumerate(filas):
        r['id'] = f'OF-{i + 1:04d}'

    # equivalencias
    pares = []
    ok = [r for r in filas if r['calidad'] == 'ok']
    for i, x in enumerate(ok):
        for y in ok[i + 1:]:
            if x['categoria'] != y['categoria'] or x['marca'] == y['marca'] or x['subtono'] != y['subtono']:
                continue
            d = de2000((x['L'], x['a'], x['b']), (y['L'], y['a'], y['b']))
            if d <= MAX_DE:
                pares.append(dict(id_a=x['id'], marca_a=x['marca'], producto_a=x['producto'], tono_a=x['tono'],
                                  id_b=y['id'], marca_b=y['marca'], producto_b=y['producto'], tono_b=y['tono'],
                                  categoria=x['categoria'], subtono=x['subtono'], delta_e00=round(d, 2)))
    pares.sort(key=lambda p: p['delta_e00'])

    campos = ['id', 'marca', 'categoria', 'producto', 'tono', 'hex', 'L', 'a', 'b', 'C', 'h', 'profundidad',
              'subtono', 'origen_subtono', 'calidad', 'nivel', 'fuente', 'fecha']
    with open(DATOS / 'tonos_oficiales.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=campos, extrasaction='ignore')
        w.writeheader()
        w.writerows(filas)
    with open(INTERMEDIOS / 'equivalencias.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(pares[0].keys()) if pares else ['id_a'])
        w.writeheader()
        w.writerows(pares)

    print(f'{len(filas)} tonos · calidad: {dict(Counter(r["calidad"] for r in filas))}')
    print(f'subtono: {dict(Counter(r["subtono"] for r in filas))} · declarado por la marca: {sum(1 for r in filas if r["subtono_declarado"])}')
    print(f'{len(pares)} equivalencias (ΔE00 <= {MAX_DE}, mismo subtono, marca distinta)')
    con = Counter()
    for p in pares:
        con[p['id_a']] += 1
        con[p['id_b']] += 1
    print(f'tonos con al menos una equivalencia: {len(con)} de {len(ok)} tonos "ok"')
    print('por par de marcas:', dict(Counter(tuple(sorted((p['marca_a'], p['marca_b']))) for p in pares).most_common(10)))


if __name__ == '__main__':
    main()
