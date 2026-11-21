"""Venta en Colombia, precio, foto y enlace por tono de los productos de color (labial, rubor, bronzer,
iluminador y sombras) de fuentes_oficiales/color_*.jsonl.

Para cada producto busca en Éxito, Falabella, Jumbo y Locatel (las mismas funciones de enlaces_tono.py). Un resultado
se acepta si es de la misma marca, tiene todas las palabras obligatorias y ninguna excluida.
- Sin resultados: el producto queda "sin venta confirmada en Colombia" y no entra a la app.
- Precio: mediana de los resultados aceptados. Foto: la del primer resultado (se descarga).
- Enlace por tono: el resultado cuyo nombre contiene el nombre o código del tono.

Salida: etl/intermedios/tiendas_color.json
Uso:    python etl/tiendas_color.py
"""
import json
import re
import statistics
from datetime import date
from pathlib import Path

from enlaces_tono import coincide_tono, curl, exito, falabella, jumbo, locatel, norm

from rutas import FOTOS, FUENTES_OFICIALES, INTERMEDIOS
SALIDA = INTERMEDIOS / 'tiendas_color.json'
EXCLUIR_SIEMPRE = ['unas', 'esmalte', 'mascara', 'pestan', 'delineador', 'liner', 'desmaquill', 'kit regalo', 'tripack']
# Búsquedas cuyas palabras clave también aparecen en otros productos de la marca (p. ej. "Lumi" es también
# un iluminador): para estos la venta solo se confirma si algún resultado trae el nombre de un tono del producto.
REQUIERE_TONO = {"L'Oréal Paris|Lumi Liquid Blush Rubor Líquido", "L'Oréal Paris|Color Riche Matte Labial en Barra",
                 'Max Factor|Lipfinity Lipstick', 'Max Factor|Bronzer Polvo', 'Maybelline|Fit Me Rubor',
                 'Maybelline|SuperStay Vinyl Ink Pinks', 'Maybelline|Cloudtopia Rubor en Mousse',
                 'Maybelline|Sunkisser Hazy Matte Blush'}
# Nombre con que la tienda publica el tono cuando difiere del oficial
ALIAS_TONO = {('Max Factor|Masterpiece Nude Palette', 'Cappucino Nudes'): 'capuchino',
              ('Maybelline|Color Rivals Dúo de Sombras', 'Assertive x Coy'): 'asser coy'}

# Versiones vistas a mano en la página del producto en la tienda (el listado de búsqueda no trae el nombre)
OFERTAS_MANUALES = {
    'Estée Lauder|The Essential Eyeshadow Quad': {
        t: [dict(tienda='Falabella', url='https://www.falabella.com.co/falabella-co/product/prod13920117/'
                 'Paleta-de-rostro-Compacto-Sombras-de-ojos-Pure-Colour-Essential-Quad-4', precio=263990, disponible=True)]
        for t in ('Getaway', 'Money Moves', 'Gallery Hop', 'Power Brunch', 'Apres Spree')},
    # Farmatodo no tiene API pública: páginas revisadas en el navegador ("Disponible en tienda", $25.500)
    'Essence|The Nude Edition Eyeshadow Palette': {'The Nude Edition': [dict(
        tienda='Farmatodo', url='https://www.farmatodo.com.co/producto/216000042-paleta-sombras-essence-nude-x-10-gr',
        precio=25500, disponible=True)]},
    'Essence|The Brown Edition Eyeshadow Palette': {'The Brown Edition': [dict(
        tienda='Farmatodo', url='https://www.farmatodo.com.co/producto/227200082-paleta-de-sombras-essence-the-brown-tono-30-x-10-gr',
        precio=25500, disponible=True)]},
}

# producto -> (búsqueda, palabras obligatorias, palabras excluidas)
BUSQUEDA = {
    'Vogue|Labial Colorissimo Barra Larga Duración': ('vogue labial colorissimo barra', ['colorissimo', 'barra'], ['liquid', 'brillo', 'balsamo', 'volumen']),
    'Vogue|Labial Colorissimo Líquido Mate': ('vogue colorissimo liquido mate', ['colorissimo', 'liquid'], ['brillo']),
    'Vogue|Labial Colorissimo Extra Brillo': ('vogue colorissimo extra brillo', ['colorissimo', 'brillo'], ['volumen']),
    'Vogue|Labial Líquido Resist': ('vogue labial liquido resist', ['resist', 'labial'], ['brillo', 'base', 'corrector', 'polvo']),
    'Vogue|Bálsamo Colorissimo Mua': ('vogue balsamo mua', ['mua'], []),
    'Vogue|Brillo Colorissimo Extra Volumen': ('vogue brillo extra volumen', ['volumen'], []),
    'Vogue|Labial Boombastic': ('vogue boombastic', ['boombastic'], []),
    'Vogue|Labial Brillante Resist Oh Q Brillo': ('vogue oh q brillo', ['oh q brillo'], []),
    'Vogue|Rubor Líquido TQM': ('vogue rubor tqm', ['tqm'], []),
    'Vogue|Rubor Compacto': ('vogue rubor compacto', ['rubor'], ['tqm', 'liquid']),
    'Maybelline|SuperStay Matte Ink Labial Líquido': ('maybelline superstay matte ink', ['matte ink'], []),
    'Maybelline|SuperStay Vinyl Ink': ('maybelline vinyl ink', ['vinyl'], []),
    'Maybelline|SuperStay Vinyl Ink Pinks': ('maybelline vinyl ink', ['vinyl'], []),
    'Maybelline|SuperStay Teddy Tint': ('maybelline teddy tint', ['teddy'], []),
    'Maybelline|Lifter Gloss con Ácido Hialurónico': ('maybelline lifter gloss', ['lifter', 'gloss'], ['plump', 'glaze']),
    'Maybelline|Lifter Plump': ('maybelline lifter plump', ['plump'], []),
    'Maybelline|Lifter Glaze Bálsamo con Color': ('maybelline lifter glaze', ['glaze'], []),
    'Maybelline|Cloudtopia Rubor en Mousse': ('maybelline rubor', ['rubor'], ['matte', 'liquid']),
    'Maybelline|Sunkisser Hazy Matte Blush': ('maybelline rubor', ['rubor', 'matte'], []),
    'Maybelline|Sunkisser Blush Rubor Líquido': ('maybelline sunkisser', ['sunkisser'], ['hazy']),
    'Maybelline|Fit Me Rubor': ('maybelline fit me rubor', ['fit me', 'rubor'], []),
    'Maybelline|Color Rivals Dúo de Sombras': ('maybelline sombra', ['rival'], []),
    "L'Oréal Paris|Infallible Matte Resistance Labial Líquido": ('loreal infallible labial liquido matte', ['infallible', 'matte', 'labial'], ['base', 'laque']),
    "L'Oréal Paris|Infallible Laque Resistance Labial Líquido": ('loreal laque resistance', ['laque'], []),
    "L'Oréal Paris|Color Riche Matte Labial en Barra": ('loreal color riche matte', ['color riche'], ['volume', 'luminous', 'nudes']),
    "L'Oréal Paris|Color Riche Intense Volume Matte": ('loreal color riche intense volume matte', ['volume'], []),
    "L'Oréal Paris|Hyaluron Tint Tinta Sérum": ('loreal hyaluron tint', ['hyaluron', 'tint'], []),
    "L'Oréal Paris|Plump Ambition Lip Oil": ('loreal plump ambition', ['plump'], []),
    "L'Oréal Paris|Color Riche Luminous Labial en Barra": ('loreal color riche luminous', ['luminous'], []),
    "L'Oréal Paris|Color Riche Nudes of Worth": ('loreal nudes of worth', ['nudes of worth'], []),
    "L'Oréal Paris|Lumi Liquid Blush Rubor Líquido": ('loreal lumi blush', ['lumi'], ['base', 'glotion']),
    "L'Oréal Paris|Infallible Soft Matte Bronzer": ('loreal infallible bronzer', ['bronzer'], []),
    "L'Oréal Paris|Paradise Le Shadow Stick": ('loreal shadow stick', ['shadow'], []),
    'Max Factor|Colour Elixir Lipstick': ('max factor colour elixir', ['elixir'], ['gloss']),
    'Max Factor|Lipfinity Lipstick': ('max factor lipfinity lipstick', ['lipfinity'], []),
    'Max Factor|Lipfinity Lip Colour': ('max factor lipfinity', ['lipfinity'], []),
    'Max Factor|Honey Lacquer Gloss': ('max factor honey lacquer', ['honey lacquer'], []),
    'Max Factor|Velvet Mattes Lipstick': ('max factor velvet mattes', ['velvet'], []),
    'Max Factor|Bronzer Polvo': ('max factor bronzer', ['bron'], ['base', 'corrector', 'facefinity', 'miracle', 'labial', 'lipfinity']),
    'Max Factor|Facefinity Blush': ('max factor facefinity blush', ['facefinity', 'blush'], []),
    'Max Factor|Creme Puff Blush': ('max factor creme puff blush', ['creme puff', 'blush'], []),
    'Max Factor|Masterpiece Nude Palette': ('max factor sombra', ['masterpiece'], []),
    'Max Factor|Smokey Eye Drama Kit': ('max factor smokey eye drama', ['smokey'], []),
    'Essence|The Nude Edition Eyeshadow Palette': ('essence nude', ['essence', 'nude'], ['labial', 'lip', 'brillo', 'base', 'rubor']),
    'Essence|The Rose Edition Eyeshadow Palette': ('essence rose', ['essence', 'rose'], ['labial', 'lip', 'brillo', 'base', 'rubor']),
    'Essence|The Brown Edition Eyeshadow Palette': ('essence brown', ['essence', 'brown'], ['labial', 'lip', 'brillo', 'base', 'rubor', 'ceja', 'brow']),
    'Estée Lauder|The Essential Eyeshadow Quad': ('estee lauder quad', ['quad'], []),
    'Clinique|Almost Lipstick Bálsamo Labial': ('clinique almost lipstick', ['almost'], []),
    'Clinique|Clinique Pop Longwear Lipstick': ('clinique pop lipstick', ['pop'], ['plush', 'cheek', 'gloss', 'oil']),
    'Clinique|Chubby Stick Moisturizing Lip Colour Balm': ('clinique chubby stick lip', ['chubby stick'], ['cheek', 'contour', 'highlight', 'sculpting']),
    'Clinique|Pop Plush Creamy Lip Gloss': ('clinique pop plush', ['plush'], []),
    'Clinique|Pop Lip + Cheek Oil': ('clinique pop lip cheek oil', ['oil'], []),
    'Clinique|Daily Calm Lip + Cheek Color': ('clinique daily calm lip cheek', ['daily calm', 'lip'], []),
    'Clinique|Cheek Pop Blush': ('clinique cheek pop', ['cheek pop'], []),
    'Clinique|Blushing Blush Powder Blush': ('clinique blushing blush', ['blushing blush'], []),
    'Clinique|Chubby Stick Cheek Colour Balm': ('clinique rubor', ['chubby'], []),
    'Clinique|True Bronze Pressed Powder Bronzer': ('clinique true bronze', ['true bronze'], []),
    'Clinique|Chubby Stick Sculpting Contour': ('clinique chubby stick contour', ['contour'], []),
    'Clinique|Chubby Stick Sculpting Highlight': ('clinique iluminador', ['chubby', 'iluminador'], []),
    'Clinique|True Highlight Weightless Illuminator': ('clinique iluminador', ['true highlight'], []),
    'Clinique|High Impact Shadow Play Shadow + Definer': ('clinique shadow play', ['shadow play'], []),
    'Clinique|All About Shadow Single': ('clinique all about shadow', ['all about shadow'], ['duo', 'quad']),
    'Clinique|All About Shadow Duo': ('clinique all about shadow duo', ['all about shadow', 'duo'], []),
    'Clinique|All About Shadow Quad': ('clinique all about shadow quad', ['quad'], []),
}


def productos():
    for f in sorted((FUENTES_OFICIALES).glob('color_*.jsonl')):
        for linea in f.read_text(encoding='utf-8').splitlines():
            if linea.strip():
                yield json.loads(linea)


def main():
    FOTOS.mkdir(parents=True, exist_ok=True)
    salida, cache = {}, {}
    for p in productos():
        clave = f"{p['marca']}|{p['nombre']}"
        if clave not in BUSQUEDA:
            print(f'  sin búsqueda definida: {clave}')
            continue
        q, oblig, excl = BUSQUEDA[clave]
        if q not in cache:
            cache[q] = exito(q) + falabella(q) + jumbo(q) + locatel(q)
        marca = norm(p['marca']).replace(' paris ', ' ').strip().replace(' ', '')
        validos = []
        for r in cache[q]:
            texto = norm(r['producto'] + ' ' + r['variante'] + ' ' + r['marca'])
            if marca not in texto.replace(' ', '') or r['precio'] <= 0:
                continue
            if r['marca'] and marca not in norm(r['marca']).replace(' ', ''):
                continue                                   # p. ej. Dior "Essence de Rose" no es de la marca Essence
            if all(norm(k).strip() in texto for k in oblig) and not any(norm(k).strip() in texto for k in excl + EXCLUIR_SIEMPRE):
                validos.append((texto, r))
        nombres = [t[0] for t in p.get('tonos', [])] + [x['nombre'] for x in p.get('paletas', [])]
        por_tono = {}
        for tono in nombres:
            ofertas, vistos = [], set()
            for texto, r in sorted(validos, key=lambda v: (not v[1]['disponible'], v[1]['precio'])):
                if coincide_tono(texto, ALIAS_TONO.get((clave, tono), tono)) and r['url'] not in vistos:
                    vistos.add(r['url'])
                    ofertas.append(dict(tienda=r['tienda'], url=r['url'], precio=r['precio'], disponible=r['disponible']))
            for o in OFERTAS_MANUALES.get(clave, {}).get(tono, []):
                if o['url'] not in vistos:
                    ofertas.append(o)
            if ofertas:
                por_tono[tono] = ofertas[:3]
        # Muchas tiendas publican el producto sin el nombre del tono: basta con las palabras clave,
        # salvo en los productos de REQUIERE_TONO
        manuales = [o for os in OFERTAS_MANUALES.get(clave, {}).values() for o in os]
        if not (validos or manuales) or (clave in REQUIERE_TONO and not por_tono):
            print(f'  sin venta confirmada: {clave}  ({len(validos)} resultados, 0 tonos)')
            continue
        precio = int(statistics.median([r['precio'] for _, r in validos] + [o['precio'] for o in manuales]))
        primero = validos[0][1] if validos else manuales[0]
        con_foto = next((r for _, r in validos if r.get('imagen')), None)
        archivo = re.sub(r'\s+', '-', norm(clave.replace('|', ' ')).strip())[:80] + '.jpg'
        foto = ''
        if con_foto:
            img = curl(con_foto['imagen'].split('?')[0])
            if len(img) > 2000:
                (FOTOS / archivo).write_bytes(img)
                foto = f'/static/img/products/oficial/{archivo}'
        tiendas = sorted({r['tienda'] for _, r in validos} | {o['tienda'] for o in manuales})
        salida[clave] = dict(precio_cop=precio, url=primero['url'], tienda=primero['tienda'], imagen=foto,
                             fuente=f"{' y '.join(tiendas)} Colombia (mediana de {len(validos) + len(manuales)} resultados)",
                             fecha=str(date.today()), tonos=por_tono)
        print(f'  ok  {clave}  ${precio:,}  {len(por_tono)}/{len(nombres)} tonos con enlace')
    json.dump(salida, open(SALIDA, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'{len(salida)} productos de color con venta confirmada en Colombia')


if __name__ == '__main__':
    main()
