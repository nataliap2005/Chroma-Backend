"""Genera los diagramas de Chroma en SVG (y PNG en macOS).

Uso, desde la carpeta Chroma-Backend:
    python docs/diagramas/generar_diagramas.py

Los SVG se escriben siempre. Los PNG se crean con Quick Look (qlmanage, incluido en macOS) y
Pillow; en otros sistemas se pueden exportar abriendo el SVG en el navegador.
"""
import csv
import shutil
import subprocess
import tempfile
from collections import Counter
from html import escape
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
RAIZ = CARPETA.parents[1]

# Colores de la marca
VINO, TINTA, GRIS, LINEA, CREMA = '#7e1738', '#24191a', '#6f6466', '#d9cdc9', '#fffaf7'
CAPA = {  # relleno, borde
    'app': ('#f9e9ee', '#c98a9e'), 'api': ('#f3e3f0', '#a7739a'), 'datos': ('#e4f4ec', '#6fb391'),
    'ext': ('#eef0f4', '#9aa3b5'), 'etl': ('#fdf1e2', '#d3a15c'), 'gente': ('#fff', VINO), 'ia': ('#e8eefb', '#7d93c9'),
}
FUENTE = 'Helvetica, Arial, sans-serif'


class Lienzo:
    def __init__(self, ancho, alto, titulo, subtitulo=''):
        self.w, self.h = ancho, alto
        self.partes = [f'<rect width="{ancho}" height="{alto}" fill="{CREMA}"/>',
                       self.texto(40, 52, titulo, 30, VINO, 'bold'),
                       self.texto(40, 82, subtitulo, 16, GRIS) if subtitulo else '']

    @staticmethod
    def texto(x, y, t, size=15, color=TINTA, peso='normal', anchor='start'):
        return (f'<text x="{x}" y="{y}" font-family="{FUENTE}" font-size="{size}" fill="{color}" '
                f'font-weight="{peso}" text-anchor="{anchor}">{escape(t)}</text>')

    def caja(self, x, y, w, h, titulo, lineas=(), capa='app', radio=14, centro=True):
        relleno, borde = CAPA[capa]
        self.partes.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radio}" fill="{relleno}" stroke="{borde}" stroke-width="2"/>')
        cx = x + w / 2 if centro else x + 16
        anchor = 'middle' if centro else 'start'
        total = 24 + 20 * len(lineas)
        y0 = y + (h - total) / 2 + 18
        self.partes.append(self.texto(cx, y0, titulo, 18, TINTA, 'bold', anchor))
        for i, l in enumerate(lineas):
            self.partes.append(self.texto(cx, y0 + 24 + 20 * i, l, 14, GRIS, 'normal', anchor))
        return (x, y, w, h)

    def flecha(self, x1, y1, x2, y2, etiqueta='', punteada=False, color=GRIS, doble=False, dx=0, dy=0):
        dash = ' stroke-dasharray="7 6"' if punteada else ''
        ini = ' marker-start="url(#pi)"' if doble else ''
        self.partes.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="2"{dash} marker-end="url(#pf)"{ini}/>')
        if etiqueta:
            self.etiqueta((x1 + x2) / 2 + dx, (y1 + y2) / 2 + dy, etiqueta)

    def etiqueta(self, x, y, t, size=13):
        lineas = t.split('\n')
        ancho = max(len(l) for l in lineas) * size * 0.56 + 14
        alto = 18 * len(lineas) + 6
        self.partes.append(f'<rect x="{x - ancho / 2}" y="{y - alto / 2}" width="{ancho}" height="{alto}" rx="6" fill="#fff" stroke="{LINEA}"/>')
        for i, l in enumerate(lineas):
            self.partes.append(self.texto(x, y - alto / 2 + 17 + 18 * i, l, size, TINTA, 'normal', 'middle'))

    def svg(self):
        defs = (f'<defs><marker id="pf" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">'
                f'<path d="M0,0 L10,5 L0,10 z" fill="{GRIS}"/></marker>'
                f'<marker id="pi" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">'
                f'<path d="M0,0 L10,5 L0,10 z" fill="{GRIS}"/></marker></defs>')
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}">'
                + defs + ''.join(self.partes) + '</svg>\n')


# ----------------------------------------------------------------------------- diagramas

def arquitectura():
    c = Lienzo(1600, 880, 'Arquitectura de Chroma', 'Beta publicada en Render con dominio propio; datos y cuentas en Supabase')
    c.caja(40, 380, 200, 130, 'Usuaria', ['celular o', 'computador'], 'gente')
    c.caja(330, 330, 340, 230, 'Chroma App', ['Ionic React + Capacitor', 'web y Android', 'Render · sitio estático', 'chroma-app.estefania.dev'], 'app')
    c.caja(820, 130, 340, 230, 'Chroma API', ['FastAPI · Python', 'colorimetría, catálogo, traductor,', 'asesor, planes y pagos', 'Render · web service'], 'api')
    c.caja(820, 560, 340, 240, 'Supabase', ['Auth: cuentas y sesiones', 'PostgreSQL con RLS: perfiles, test,', 'opiniones, planes, catálogo, pagos', 'Storage: fotos de perfil y productos'], 'datos')
    c.caja(1290, 110, 270, 120, 'Wompi', ['pagos de Plus y Premium'], 'ext')
    c.caja(1290, 310, 270, 120, 'Resend', ['correos de cuenta y de pago'], 'ext')
    c.caja(1290, 600, 270, 150, 'ETL del catálogo', ['fuentes oficiales y tiendas', 'scripts en etl/', '(se corre fuera de línea)'], 'etl')
    c.flecha(240, 445, 330, 445, 'HTTPS', dy=-22)
    c.flecha(670, 390, 820, 280, 'test, catálogo, traductor,\nasesor y pagos', dx=-45, dy=-45)
    c.flecha(670, 500, 820, 640, 'cuentas, perfil, opiniones,\nadministración (RLS)', dx=-60, dy=40)
    c.flecha(990, 360, 990, 560, 'planes, cuotas,\ncatálogo, pagos', dx=0)
    c.flecha(1160, 180, 1290, 170, 'checkout firmado', dy=-20)
    c.flecha(1290, 200, 1160, 220, 'evento de pago', dy=22)
    c.flecha(1160, 290, 1290, 350, 'confirmación\nde pago', dx=10, dy=-4)
    c.flecha(1160, 590, 1310, 430, 'correos de cuenta (SMTP)', dx=40, dy=0)
    c.flecha(1290, 680, 1160, 680, 'carga del catálogo', dy=-20)
    return c


def modelo_datos():
    c = Lienzo(1900, 1090, 'Modelo de datos (Supabase · PostgreSQL)',
               'Línea continua: llave foránea a auth.users (al borrar la cuenta se borran sus datos). Punteada: referencia por id de producto.')

    def entidad(x, y, nombre, cols, capa='datos', w=360):
        relleno, borde = CAPA[capa]
        h = 46 + 24 * len(cols)
        c.partes.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="#fff" stroke="{borde}" stroke-width="2"/>')
        c.partes.append(f'<rect x="{x}" y="{y}" width="{w}" height="38" rx="10" fill="{relleno}" stroke="{borde}" stroke-width="2"/>')
        c.partes.append(c.texto(x + 14, y + 26, nombre, 17, TINTA, 'bold'))
        for i, (col, tipo) in enumerate(cols):
            c.partes.append(c.texto(x + 14, y + 64 + 24 * i, col, 14, TINTA, 'bold' if 'PK' in tipo else 'normal'))
            c.partes.append(c.texto(x + w - 14, y + 64 + 24 * i, tipo, 13, GRIS, 'normal', 'end'))
        return x, y, w, h

    A, B, C, D = 40, 560, 1060, 1500
    perfiles = entidad(A, 120, 'profiles', [('user_id', 'PK · FK'), ('display_name', 'text'), ('avatar_path', 'text')])
    test = entidad(A, 290, 'colorimetry_results', [('id', 'PK'), ('user_id', 'FK'), ('answers', 'jsonb'), ('analysis', 'jsonb'), ('season · undertone', 'text'), ('created_at', 'fecha')])
    planes = entidad(A, 530, 'user_plans', [('user_id', 'PK · FK'), ('plan', 'free | plus | premium'), ('is_admin', 'bool'), ('plan_expires_at', 'fecha')])
    uso = entidad(A, 720, 'usage_monthly', [('user_id · mes', 'PK · FK'), ('traductor · looks', 'int')])
    pagos = entidad(A, 850, 'payments', [('reference', 'PK'), ('user_id', 'FK'), ('plan · amount_in_cents', ''), ('status', 'PENDING | APPROVED …')])
    usuarios = entidad(B, 430, 'auth.users', [('id', 'PK'), ('email', 'text'), ('created_at', 'fecha')], 'gente', 320)
    fav = entidad(C, 120, 'favorites', [('user_id · product_id', 'PK · FK')])
    cos = entidad(C, 230, 'vanity (cosmetiquera)', [('user_id · product_id', 'PK · FK')])
    tono = entidad(C, 340, 'tone_feedback', [('user_id · product_id', 'PK · FK'), ('tono_resultado', 'acertado | parcial | …'), ('motivo_tono · comment', 'text'), ('confidence_before · after', '1 a 5')])
    look = entidad(C, 560, 'look_feedback', [('id', 'PK'), ('user_id', 'FK'), ('occasion · budget', ''), ('product_ids', 'text[]'), ('le_gusta · lo_usaria', ''), ('comment', 'text')])
    cat = entidad(D, 260, 'catalog_products', [('id', 'PK · CH-5001…'), ('nombre · marca', 'text'), ('categoria · tono', 'text'), ('color_hex', '#RRGGBB'), ('subtono · profundidad', 'text'), ('precio_cop', 'int'), ('activo', 'bool')], 'etl')
    marcas = entidad(D, 560, 'brand_plans', [('marca', 'PK'), ('plan', 'free | plus | premium')], 'etl')

    ux, uy, uw, uh = usuarios
    for i, (x, y, w, h) in enumerate([perfiles, test, planes, uso, pagos]):
        c.flecha(x + w, y + 24, ux, uy + 30 + i * 20)
    for i, (x, y, w, h) in enumerate([fav, cos, tono, look]):
        c.flecha(x, y + 24, ux + uw, uy + 40 + i * 20)
    cx, cy, cw, ch = cat
    for i, (x, y, w, h) in enumerate([fav, cos, tono, look]):
        c.flecha(x + w, y + 24, cx, cy + 40 + i * 30, punteada=True)
    mx, my, mw, mh = marcas
    c.flecha(mx + mw / 2, my, mx + mw / 2, cy + ch, 'marca', punteada=True, dx=40)
    c.etiqueta(950, 1045, 'RLS en todas las tablas: cada usuaria solo ve y cambia lo suyo; las administradoras usan funciones verificadas en la base de datos')
    return c


def etl_catalogo():
    c = Lienzo(1760, 660, 'ETL del catálogo', 'Extracción → transformación → carga. tests/test_etl.py comprueba que regenera el catálogo idéntico')
    for x, t in [(40, 'EXTRACCIÓN'), (380, 'DATOS CRUDOS'), (720, 'TRANSFORMACIÓN'), (1060, 'CARGA'), (1400, 'DESTINO')]:
        c.partes.append(c.texto(x, 130, t, 14, VINO, 'bold'))
    c.caja(40, 160, 290, 140, 'Páginas oficiales', ['7 marcas · color de cada tono', '(navegador)'], 'ext')
    c.caja(380, 160, 290, 140, 'fuentes_oficiales/', ['*.json · color_*.jsonl', '+ fotos de paletas'], 'etl')
    c.caja(720, 160, 290, 140, 'procesar_tonos_*.py', ['subtono (CIELAB), calidad,', 'equivalencias ΔE00 ≤ 3'], 'etl')
    c.caja(40, 400, 290, 140, 'Tiendas colombianas', ['Éxito, Falabella,', 'Jumbo, Locatel'], 'ext')
    c.caja(380, 400, 290, 140, 'Scripts de tiendas', ['precios_*.py · enlaces_tono.py', 'tiendas_color.py', '→ etl/intermedios/*.json'], 'etl')
    c.caja(720, 400, 290, 140, 'tonos_oficiales.csv', ['tonos_color.csv', 'equivalencias.csv'], 'etl')
    c.caja(1060, 270, 290, 150, 'importar_mi_base.py', ['solo productos vendidos en', 'Colombia · ids fijos'], 'etl')
    c.caja(1400, 150, 320, 100, 'productos_mvp.csv', ['688 productos · 7 marcas'], 'api')
    c.caja(1400, 300, 320, 100, 'export_catalog_sql.py', ['→ 006_catalogo_inicial.sql'], 'api')
    c.caja(1400, 450, 320, 120, 'Supabase · catalog_products', ['luego lo mantienen las', 'administradoras desde la app'], 'datos')
    c.flecha(330, 230, 380, 230)
    c.flecha(670, 230, 720, 230)
    c.flecha(865, 300, 865, 400)
    c.flecha(330, 470, 380, 470)
    c.flecha(1010, 470, 1060, 380)
    c.partes.append(f'<path d="M525,540 C525,615 1205,615 1205,421" fill="none" stroke="{GRIS}" stroke-width="2" marker-end="url(#pf)"/>')
    c.etiqueta(865, 598, 'precios, enlaces y venta en Colombia')
    c.flecha(1350, 320, 1400, 220)
    c.flecha(1560, 250, 1560, 300)
    c.flecha(1560, 400, 1560, 450)
    return c


def flujo_usuaria():
    c = Lienzo(1760, 600, 'Recorrido de la usuaria', 'Del registro a la opinión que alimenta los indicadores y el futuro modelo de IA')
    c.caja(40, 250, 170, 110, 'Inicio', ['botones grandes', 'de registro'], 'gente')
    c.caja(270, 150, 210, 110, 'Crear cuenta', ['o ingresar'], 'app')
    c.caja(270, 350, 210, 110, 'Test sin cuenta', ['se guarda y pasa', 'a la cuenta'], 'app')
    c.caja(540, 250, 210, 110, 'Test', ['27 preguntas', 'con fotos y colores'], 'app')
    c.caja(810, 250, 220, 110, 'Resultado', ['estación, subtono', 'y paleta'], 'api')
    c.caja(1090, 120, 250, 100, 'Catálogo', ['ordenado por compatibilidad'], 'app')
    c.caja(1090, 255, 250, 100, 'Traductor de tonos', ['mismo color, otra marca'], 'app')
    c.caja(1090, 390, 250, 100, 'Asesor por ocasión', ['look con presupuesto'], 'app')
    c.caja(1400, 180, 320, 120, 'Opiniones', ['¿acertó el tono? · ¿te gusta', 'el look? · ¿lo usarías?'], 'datos')
    c.caja(1400, 360, 320, 120, 'Panel de resultados', ['KR1 · KR2 · KR3', 'y datos para el modelo de IA'], 'ia')
    c.flecha(210, 280, 270, 220)
    c.flecha(210, 330, 270, 400)
    c.flecha(480, 210, 540, 280)
    c.flecha(480, 400, 540, 330)
    c.flecha(750, 305, 810, 305)
    for y in (170, 305, 440):
        c.flecha(1030, 305, 1090, y)
    for y in (170, 305, 440):
        c.flecha(1340, y, 1400, 240)
    c.flecha(1560, 300, 1560, 360)
    return c


def flujo_pago():
    c = Lienzo(1600, 820, 'Flujo de pago (Wompi)', 'El plan se activa por el evento firmado de Wompi o al volver a la app; nunca dos veces')
    carriles = [('App', 150), ('Chroma API', 480), ('Supabase', 810), ('Wompi', 1140), ('Resend', 1450)]
    for nombre, x in carriles:
        c.caja(x - 110, 120, 220, 60, nombre, [], 'ext' if nombre in ('Wompi', 'Resend') else 'datos' if nombre == 'Supabase' else 'api' if 'API' in nombre else 'app')
        c.partes.append(f'<line x1="{x}" y1="180" x2="{x}" y2="780" stroke="{LINEA}" stroke-width="2" stroke-dasharray="6 6"/>')
    X = dict(carriles)
    pasos = [
        ('App', 'Chroma API', '1. POST /checkout (plan + sesión)'),
        ('Chroma API', 'Supabase', '2. registra el pago (PENDING)'),
        ('Chroma API', 'App', '3. URL de Wompi con firma de integridad'),
        ('App', 'Wompi', '4. la usuaria paga (tarjeta, PSE, Nequi)'),
        ('Wompi', 'Chroma API', '5. evento firmado (webhook)'),
        ('Chroma API', 'Supabase', '6. apply_payment → plan por 30 días'),
        ('Chroma API', 'Resend', '7. correo de confirmación'),
        ('App', 'Chroma API', '8. al volver: GET /status?id='),
        ('Chroma API', 'Wompi', '9. consulta el estado real'),
    ]
    for i, (a, b, t) in enumerate(pasos):
        y = 230 + i * 60
        x1, x2 = X[a], X[b]
        c.flecha(x1 + (8 if x2 > x1 else -8), y, x2 + (-8 if x2 > x1 else 8), y)
        c.etiqueta((x1 + x2) / 2, y - 16, t)
    return c


def motor_colorimetria():
    c = Lienzo(1760, 470, 'Motor de colorimetría y compatibilidad (reglas actuales)',
               'Heurística explicable: cada respuesta suma evidencia en cuatro ejes; el modelo de IA la complementará')
    c.caja(40, 200, 230, 150, '27 respuestas', ['piel, venas, joyas,', 'cabello, ojos, colores'], 'app')
    c.caja(330, 140, 280, 270, '4 ejes de color', ['temperatura: frío ↔ cálido', 'profundidad: claro ↔ profundo', 'saturación: suave ↔ brillante', 'contraste: bajo ↔ alto', '(cada pista tiene un peso)'], 'api')
    c.caja(670, 200, 250, 150, '12 estaciones', ['distancia a cada', 'perfil de referencia'], 'api')
    c.caja(980, 200, 250, 150, 'Resultado', ['estación, subtono,', 'paleta y confianza'], 'api')
    c.caja(1290, 110, 430, 330, 'Compatibilidad 0–100', ['por cada producto del catálogo:', '', 'claridad del tono · 28', 'subtono · 25', 'estación · 17', 'tipo de piel · 10', 'acabado · 10', 'presupuesto · 10', '+ ajuste por la opinión de la usuaria'], 'datos')
    c.flecha(270, 275, 330, 275)
    c.flecha(610, 275, 670, 275)
    c.flecha(920, 275, 980, 275)
    c.flecha(1230, 275, 1290, 275)
    return c


def plan_ia():
    c = Lienzo(1760, 700, 'Plan del modelo de IA', 'Aprender de lo que pasa en la app qué tonos le funcionan de verdad a cada persona')
    pasos = [
        ('Datos de uso', ['test · opiniones de tonos', 'y looks · favoritos ·', 'cosmetiquera · eventos'], 'datos'),
        ('Conjunto anónimo', ['persona × producto', 'sin correos ni nombres'], 'etl'),
        ('Entrenamiento', ['regresión logística →', 'gradient boosting →', 'recomendación colaborativa'], 'ia'),
        ('Evaluación', ['AUC · precisión top 5', 'equidad por tono de piel', 'vs. reglas actuales'], 'ia'),
        ('Producción', ['mezcla reglas + modelo', 'prueba A/B · versión', 'guardada en cada uso'], 'api'),
    ]
    for i, (t, l, capa) in enumerate(pasos):
        c.caja(40 + i * 345, 140, 300, 170, t, l, capa)
        if i:
            c.flecha(40 + i * 345 - 45, 225, 40 + i * 345, 225)
    c.partes.append(f'<path d="M1520,310 C1520,400 190,400 190,320" fill="none" stroke="{GRIS}" stroke-width="2" stroke-dasharray="7 6" marker-end="url(#pf)"/>')
    c.etiqueta(855, 378, 'reentrenar cada mes o cada 500 opiniones nuevas')
    c.partes.append(c.texto(40, 470, 'FASES', 14, VINO, 'bold'))
    fases = [('Fase 0 · beta (ahora)', '~30 personas: recopilar y medir KR1–KR3'),
             ('Fase 1', '≥ 300 opiniones: análisis y regresión logística'),
             ('Fase 2', '≥ 2.000 opiniones: boosting y prueba A/B'),
             ('Fase 3', 'miles de interacciones: recomendación colaborativa')]
    c.partes.append(f'<line x1="60" y1="530" x2="1700" y2="530" stroke="{LINEA}" stroke-width="4"/>')
    for i, (t, d) in enumerate(fases):
        x = 60 + i * 430
        c.partes.append(f'<circle cx="{x + 10}" cy="530" r="10" fill="{VINO if i == 0 else "#fff"}" stroke="{VINO}" stroke-width="3"/>')
        c.partes.append(c.texto(x, 575, t, 16, TINTA, 'bold'))
        c.partes.append(c.texto(x, 600, d, 14, GRIS))
    return c


DIAGRAMAS = {'arquitectura': arquitectura, 'modelo_datos': modelo_datos, 'etl_catalogo': etl_catalogo,
             'flujo_usuaria': flujo_usuaria, 'flujo_pago': flujo_pago, 'motor_colorimetria': motor_colorimetria,
             'plan_modelo_ia': plan_ia}


# ----------------------------------------------------------------------------- gráficos de datos

def graficos():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    with (RAIZ / 'data' / 'productos_mvp.csv').open(encoding='utf-8-sig') as f:
        filas = list(csv.DictReader(f))
    plt.rcParams.update({'font.family': ['Helvetica', 'Arial', 'DejaVu Sans'], 'font.size': 12,
                         'axes.edgecolor': LINEA, 'axes.labelcolor': TINTA, 'xtick.color': GRIS, 'ytick.color': TINTA})

    def barras(conteo, titulo, nombre, nota):
        datos = sorted(conteo.items(), key=lambda kv: kv[1])
        fig, ax = plt.subplots(figsize=(10, 0.55 * len(datos) + 1.6), dpi=160)
        fig.patch.set_facecolor(CREMA)
        ax.set_facecolor(CREMA)
        etiquetas, valores = zip(*datos)
        ax.barh(etiquetas, valores, color=VINO, height=0.55)
        for i, v in enumerate(valores):
            ax.text(v + max(valores) * 0.01, i, str(v), va='center', color=TINTA, fontsize=11)
        ax.set_xlim(0, max(valores) * 1.12)
        for lado in ('top', 'right', 'left'):
            ax.spines[lado].set_visible(False)
        ax.tick_params(axis='y', length=0)
        ax.xaxis.grid(True, color='#ece2de', linewidth=0.8)
        ax.set_axisbelow(True)
        fig.suptitle(titulo, x=0.02, ha='left', fontsize=17, fontweight='bold', color=VINO)
        ax.set_title(nota, loc='left', fontsize=11, color=GRIS, pad=10)
        fig.tight_layout()
        for ext in ('svg', 'png'):
            fig.savefig(CARPETA / f'{nombre}.{ext}', facecolor=CREMA)
        plt.close(fig)

    barras(Counter(r['categoria'] for r in filas), 'Catálogo por categoría', 'catalogo_por_categoria',
           f'{len(filas)} productos, todos con el color oficial de la marca')
    barras(Counter(r['marca'] for r in filas), 'Catálogo por marca', 'catalogo_por_marca',
           'Free: Vogue, Maybelline, L\'Oréal Paris, Max Factor, Clinique · Plus: Essence · Premium: Estée Lauder')
    barras(Counter({'frío': 0, 'neutro': 0, 'cálido': 0} | Counter({'frio': 'frío', 'calido': 'cálido', 'neutro': 'neutro'}[r['subtono']] for r in filas)),
           'Catálogo por subtono', 'catalogo_por_subtono', 'Subtono declarado por la marca o calculado con CIELAB')


# ----------------------------------------------------------------------------- exportar

def a_png(svg: Path, ancho: int, alto: int) -> bool:
    """SVG → PNG al doble de resolución con Quick Look (macOS). Se convierte un lienzo cuadrado
    (Quick Look solo escala bien los cuadrados) y luego se recorta al tamaño real."""
    if not shutil.which('qlmanage'):
        return False
    from PIL import Image
    lado = max(ancho, alto)
    px = lado * 2
    contenido = svg.read_text(encoding='utf-8')
    contenido = contenido.replace(f'width="{ancho}" height="{alto}" viewBox="0 0 {ancho} {alto}"',
                                  f'width="{lado}" height="{lado}" viewBox="0 0 {lado} {lado}"', 1)
    with tempfile.TemporaryDirectory() as tmp:
        cuadrado = Path(tmp) / svg.name
        cuadrado.write_text(contenido, encoding='utf-8')
        subprocess.run(['qlmanage', '-t', '-s', str(px), '-o', tmp, str(cuadrado)], capture_output=True, check=False)
        salida = Path(tmp) / f'{svg.name}.png'
        if not salida.exists():
            return False
        img = Image.open(salida)
        escala = img.width / lado
        img.crop((0, 0, round(ancho * escala), round(alto * escala))).save(svg.with_suffix('.png'), optimize=True)
    return True


def main():
    for nombre, fn in DIAGRAMAS.items():
        lienzo = fn()
        ruta = CARPETA / f'{nombre}.svg'
        ruta.write_text(lienzo.svg(), encoding='utf-8')
        print(nombre, 'svg + png' if a_png(ruta, lienzo.w, lienzo.h) else 'svg')
    graficos()
    print('gráficos del catálogo: svg + png')


if __name__ == '__main__':
    main()
