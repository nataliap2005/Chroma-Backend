"""Especificación única del cuestionario Chroma v2 (UI y validación en servidor)."""

def q(key, section, title, hint, options, photo=False, multi=False):
    return {"key": key, "section": section, "heading": title, "hint": hint,
            "options": [{"value": value, "label": label} for value, label in options],
            "photo": photo, "multi": multi}

NA = ('no_se', 'No estoy segura / no lo sé')
QUESTIONS = [
 q('skin_tone','Colorimetría','¿Qué profundidad tiene tu piel sin maquillaje?',
   'Esta información se usa para bases y correctores; no define por sí sola tu estación.',
   [('claro','Clara'),('medio','Media'),('oscuro','Oscura'),('profundo','Muy profunda')]),
 q('undertone_self','Colorimetría','¿Sabes cuál es tu subtono?',
   'Si no lo conoces, elige «No estoy segura». No hay una equivalencia automática entre tono de piel y subtono.',
   [('frio','Frío: rosado, azulado o rojizo'),('calido','Cálido: dorado o amarillo'),('neutro','Neutro'),('oliva','Oliva / verdoso'),NA]),
 q('veins','Colorimetría','¿De qué color ves tus venas de la muñeca con luz natural?',
   'Es una pista muy débil: el color visible de las venas NO determina tu subtono.',
   [('azules','Azules o moradas'),('verdes','Verdes'),('mixtas','Entre azules y verdes'),NA],photo=True),
 q('sun','Colorimetría','¿Qué suele pasar cuando te expones al sol?',
   'No se usará esta respuesta para decidir si tu estación es cálida o fría. Usa protector solar.',
   [('quema','Me quemo fácilmente'),('broncea','Me bronceo con facilidad'),('ambas','Me ocurre un poco de ambas'),NA]),
 q('metal','Colorimetría','¿Con qué metal se ve tu rostro más equilibrado?',
   'Compáralos cerca del rostro con luz natural, sin filtro de cámara.',
   [('plata','Plata / plata brillante'),('oro','Oro amarillo'),('ambos','Ambos se ven igual'),NA]),
 q('white','Colorimetría','¿Qué blanco armoniza mejor cerca de tu cara?',
   'Observa si hace que tu rostro se vea más uniforme o si resaltan las sombras.',
   [('puro','Blanco óptico o nieve'),('marfil','Marfil o crema'),('ambos','Ambos por igual'),NA]),
 q('clothes','Colorimetría','¿Con qué familia de colores se ve tu piel más uniforme?',
   'Elige por cómo se ve tu rostro, no por tu color favorito.',
   [('frios','Azul zafiro, fucsia frío, morado azulado'),('calidos','Coral, naranja, camel, terracota'),('ambos','Ambos por igual'),NA]),
 q('lip_temp','Colorimetría','¿Qué familia de labiales te favorece más?',
   'Piensa en dos tonos de intensidad similar sobre tus labios.',
   [('berry','Vino, cereza azulada o frambuesa fría'),('coral','Terracota, coral anaranjado o ladrillo cálido'),('ambos','Ambos'),NA]),
 q('blush_temp','Colorimetría','¿Qué color de rubor te parece más natural?',
   'Compara tonos similares de claridad e intensidad.',
   [('rosa','Rosa frío / malva'),('durazno','Durazno / coral cálido'),('ambos','Ambos'),NA]),
 q('foundation_temp','Colorimetría','Si ya usas base, ¿qué subtono te ha quedado mejor?',
   'Elige solo si lo sabes por experiencia; si nunca usaste base, selecciona «No sé».',
   [('rosado','Rosado o frío'),('dorado','Dorado o cálido'),('neutro','Neutro'),('oliva','Oliva'),NA]),
 q('hair','Colorimetría','¿Cuál es tu color natural de cabello?',
   'Considera el crecimiento natural, no reflejos ni tintes.',
   [('rubio','Rubio'),('castano','Castaño'),('negro','Negro'),('rojizo','Rojizo'),('otro','Canoso u otro')]),
 q('hair_depth','Colorimetría','¿Qué tan oscuro es tu cabello natural?',
   'Se evalúa la profundidad, no si el cabello es cálido o frío.',
   [('muy_claro','Rubio muy claro / gris muy claro'),('claro','Rubio oscuro / castaño claro'),('medio','Castaño medio'),('oscuro','Castaño oscuro / negro'),NA]),
 q('eyes','Colorimetría','¿Cuál es el color predominante de tus ojos?',
   'Usamos este dato para completar el perfil, pero no decide solo la estación.',
   [('azul','Azules'),('verde','Verdes'),('miel','Miel o avellana'),('cafe','Cafés'),('negro','Casi negros')]),
 q('eye_depth','Colorimetría','¿Qué tan oscuros se ven tus ojos en luz natural?',
   'Lo importante es la profundidad visual.',
   [('claro','Claros o translúcidos'),('medio','Intermedios'),('oscuro','Oscuros o muy profundos'),NA]),
 q('contrast','Colorimetría','¿Qué contraste hay entre tus ojos, cabello y piel?',
   'Alto: se distinguen marcadamente; bajo: tonos visualmente similares.',
   [('bajo','Bajo'),('medio','Medio'),('alto','Alto'),NA]),
 q('brow_contrast','Colorimetría','¿Qué tan marcadas se ven tus cejas frente a tu piel?',
   'Otro indicio de contraste global; la forma de la ceja no importa.',
   [('suaves','Se ven suaves o poco contrastantes'),('medias','Contraste intermedio'),('marcadas','Muy definidas u oscuras en relación con la piel'),NA]),
 q('depth_best','Colorimetría','¿Qué profundidad de colores realza mejor tu rostro?',
   'Compara prendas junto a la cara; la pregunta NO es cuál te gusta comprar.',
   [('profundos','Colores profundos: vino, azul noche, verde bosque'),('claros','Colores claros: rosa pálido, celeste, crema'),('intermedios','Intensidad media'),NA]),
 q('lip_depth','Colorimetría','¿Con qué profundidad de labial se equilibra mejor tu cara?',
   'Compara tonos con subtono parecido.',
   [('profundo','Vino, ciruela, rojo oscuro'),('claro','Rosa claro / nude suave'),('medio','Tonos medios'),NA]),
 q('chromatic_best','Colorimetría','¿Cómo te quedan los colores muy vivos o saturados?',
   'Por ejemplo, rojo intenso, fucsia vibrante o azul eléctrico cerca de la cara.',
   [('favorecen','Iluminan mi rostro'),('dominan','Resaltan demasiado; mi cara desaparece'),('intermedio','No noto diferencia clara'),NA]),
 q('muted_effect','Colorimetría','¿Cómo se ven en ti los colores empolvados o apagados?',
   'Por ejemplo, rosa viejo, malva grisáceo y verde salvia.',
   [('favorecen','Se ven armónicos y suaves'),('apagan','Me hacen ver apagada/o'),('intermedio','Me quedan parecido a los vivos'),NA]),
 q('vivid_effect','Colorimetría','Entre dos rosas, ¿cuál te favorecería más?',
   'Imagínalos con brillo y profundidad similares; cambia principalmente la saturación.',
   [('fuerte','Fucsia intenso y definido'),('polvoso','Rosa viejo o malva polvoso'),('intermedio','Un rosa intermedio'),NA]),
 q('makeup_intensity','Colorimetría','¿Qué intensidad de maquillaje armoniza más contigo?',
   'No importa si prefieres maquillarte mucho o poco: piensa en cómo se equilibran tus facciones.',
   [('definido','Labios/ojos definidos y de color intenso'),('difuminado','Tonos suaves y difuminados'),('equilibrado','Intermedia'),NA]),
 q('clear_vs_dusty','Colorimetría','¿Qué tipo de azul te favorece más?',
   'Compara cómo se ve tu piel con el color cerca del rostro.',
   [('electrico','Azul eléctrico, limpio y brillante'),('grisaceo','Azul grisáceo y apagado'),('medio','Azul de intensidad media'),NA]),
 q('season_known','Colorimetría','¿Ya conoces tu estación por un análisis previo?',
   'Opcional. Si ya tienes una estación identificada, puedes confirmarla. Si no, Chroma hará una estimación; podrás corregirla en tu perfil.',
   [( 'no_se','No, quiero ver la estimación de Chroma'),
    ('Invierno profundo','Invierno profundo'),('Invierno frío','Invierno frío'),('Invierno brillante','Invierno brillante'),
    ('Verano claro','Verano claro'),('Verano frío','Verano frío'),('Verano suave','Verano suave'),
    ('Otoño profundo','Otoño profundo'),('Otoño cálido','Otoño cálido'),('Otoño suave','Otoño suave'),
    ('Primavera clara','Primavera clara'),('Primavera cálida','Primavera cálida'),('Primavera brillante','Primavera brillante')]),
 q('skin_type','Tus preferencias','¿Cómo describirías tu tipo de piel?',
   'Observa tu piel al terminar un día normal. Esto NO permite diagnosticar condiciones cutáneas.',
   [('seca','Seca'),('mixta','Mixta'),('grasa','Grasa'),('normal','Normal'),NA]),
 q('finish','Tus preferencias','¿Qué acabado prefieres en maquillaje?',
   'No hay un acabado universalmente correcto para cada tipo de piel.',
   [('mate','Mate'),('satinado','Satinado'),('luminoso','Luminoso')]),
 q('budget','Tus preferencias','¿Cuál es tu presupuesto máximo por producto?',
   'Para ordenar recomendaciones de nuestro catálogo ficticio en pesos colombianos.',
   [('50000','Hasta $50.000 COP'),('80000','Hasta $80.000 COP'),('120000','Hasta $120.000 COP'),('180000','Hasta $180.000 COP')]),
]

QUESTION_BY_KEY = {question['key']: question for question in QUESTIONS}
QUESTIONNAIRE_VERSION = 2


def validate_questionnaire(data):
    if not isinstance(data, dict):
        raise ValueError('Debes completar el cuestionario.')
    result = {}
    for question in QUESTIONS:
        key = question['key']
        opts = {opt['value'] for opt in question['options']}
        if question['multi']:
            values = data.get(key, [])
            if not isinstance(values, list) or any(not isinstance(x, str) or x not in opts for x in values):
                raise ValueError(f'Respuesta inválida: {key}')
            result[key] = list(dict.fromkeys(values))
        else:
            response = str(data.get(key, ''))
            if response not in opts:
                raise ValueError(f'Completa la pregunta: {question["heading"]}')
            result[key] = int(response) if key == 'budget' else response
    result['_questionnaire_version'] = QUESTIONNAIRE_VERSION
    return result
