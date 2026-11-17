"""
Motor de análisis de requisitos basado en PLN (spaCy) + reglas heurísticas.

"""
import re
import unicodedata

import spacy

MODELO = "es_core_news_sm"
MIN_PALABRAS = 4  # menos que esto no alcanza para actor + deberá + verbo + objeto
_NLP = None


def precargar_modelo():
    """Carga el modelo una sola vez. Lanza RuntimeError con un mensaje claro si falta."""
    global _NLP
    if _NLP is None:
        try:
            _NLP = spacy.load(MODELO, disable=["ner"])
        except OSError as e:
            raise RuntimeError(
                f"No se encontró el modelo de spaCy '{MODELO}'.\n"
                f"Instalalo con:  python -m spacy download {MODELO}"
            ) from e
    return _NLP



def _norm(s):
    """Minúsculas y sin tildes, para comparar sin depender de la ortografía del estudiante."""
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _forma(t):
    return _norm(t.text)


def _lema(t):
    return _norm(t.lemma_)


def _obs(categoria, tipo, explicacion, sugerencia, ejemplo=None):
    return {
        "categoria": categoria,
        "tipo": tipo,
        "explicacion": explicacion,
        "sugerencia": sugerencia,
        "ejemplo": ejemplo,
    }


CAT_ESTRUCTURA = "ESTRUCTURA"
CAT_CALIDAD = "CARACTERÍSTICAS DE CALIDAD"
CAT_LINGUISTICOS = "CRITERIOS LINGÜÍSTICOS"
_ORDEN_CAT = {CAT_ESTRUCTURA: 0, CAT_CALIDAD: 1, CAT_LINGUISTICOS: 2}


# ---------------------------------------------------------------------------
# Léxicos 
# ---------------------------------------------------------------------------
ACTORES = {"sistema", "aplicacion", "software", "usuario", "cliente",
           "administrador", "plataforma"}

MODALES_FUERTES_FORMA = {"debera", "deberan"}
MODALES_DEBILES_FORMA = {"deberia", "deberian", "podria", "podrian", "debe",
                         "deben", "puede", "pueden", "podra", "podran"}

TERMINOS_AMBIGUOS = {
    "rapido", "rapidamente", "eficiente", "eficientemente", "facil", "facilmente",
    "intuitivo", "mejorado", "seguro", "flexible", "amigable", "cosa", "todo",
    "siempre", "nunca", "alguno", "varios", "mucho", "correcto", "adecuado",
    "apropiado", "optimizar", "minimizar", "maximizar", "sencillo", "agilizar",
    "estable", "robusto", "potente", "inmediato", "inmediatamente",
    "aproximadamente", "etcetera", "etc",
}
FRASES_AMBIGUAS = [
    r"sin errores", r"lo (mas|antes) \w+ posible", r"tan \w+ como sea posible",
    r"de forma (adecuada|correcta|eficiente)", r"facil de usar",
]
FRASES_ESCAPATORIA = [  # "escape clauses" que desaconseja la norma
    r"si es posible", r"de ser posible", r"cuando corresponda", r"segun corresponda",
    r"segun sea necesario", r"cuando sea necesario", r"si fuera necesario",
    r"en la medida de lo posible", r"y/o", r"entre otros", r"u otros", r"y otros",
]
FRASES_REDUNDANTES = r"\b(capaz de|capaces de|capacidad de|capacidad para)\b"
DEMOSTRATIVOS = {"esto", "eso", "aquello", "ello", "este", "esta", "ese", "esa",
                 "estos", "estas", "esos", "esas", "aquel", "aquella"}
COMPARATIVOS = {"mejor", "mejores", "peor", "peores"}
CONECTORES_COMPUESTOS = r"\b(ademas|asi como|posteriormente|luego|despues)\b"

GRUPOS_SINONIMOS = [
    ({"usuario", "cliente"}, "el rol de la persona que usa el sistema"),
    ({"sistema", "aplicacion", "software", "plataforma"}, "el software"),
]
DEPS_COMPLEMENTO = {"obj", "iobj", "obl", "obl:arg", "xcomp", "ccomp", "advcl"}


# ---------------------------------------------------------------------------
# Clasificación de modales usando lema + morfología (con respaldo por forma)
# ---------------------------------------------------------------------------
def _clasificar_modal(t):
    """Devuelve 'fuerte', 'debil' o None."""
    forma, lema = _forma(t), _lema(t)
    if forma in MODALES_FUERTES_FORMA:
        return "fuerte"
    if lema in ("deber", "poder") and t.pos_ in ("VERB", "AUX"):
        if lema == "deber" and "Fut" in t.morph.get("Tense") and "Ind" in t.morph.get("Mood"):
            return "fuerte"
        return "debil"
    if forma in MODALES_DEBILES_FORMA:
        return "debil"
    return None


# ---------------------------------------------------------------------------
# Motor principal
# ---------------------------------------------------------------------------
def aplicar_reglas_nlp(texto):
    nlp = precargar_modelo()
    doc = nlp(texto)
    texto_norm = _norm(texto)
    res = []

    palabras = [t for t in doc if not t.is_punct and not t.is_space]

    # ---- 1. ESTRUCTURA -----------------------------------------------------
    if len(palabras) < MIN_PALABRAS:
        res.append(_obs(
            CAT_ESTRUCTURA, "Estructura Sintáctica (El enunciado no cumple la estructura requerida)",
            f"El enunciado tiene solo [b]{len(palabras)} palabras[/b] y no completa la estructura formal "
            "de un requisito: [b]Actor + 'deberá' + verbo de acción + objeto + condición/restricción[/b].",
            "Reformular el enunciado completando cada componente de la estructura.",
            "Mal: «Login de usuarios» -> Mejor: «El sistema (actor) deberá (obligación) permitir "
            "(acción) al usuario iniciar sesión (objeto) con correo y contraseña (restricción)»."))

    # Actor: se busca el sujeto sintáctico, no solo la presencia de la palabra
    sujetos = [t for t in doc if t.dep_.startswith("nsubj")]
    actor_en_sujeto = any(_lema(t) in ACTORES for t in sujetos)
    actor_en_texto = any(_lema(t) in ACTORES for t in doc)
    if not actor_en_texto:
        res.append(_obs(
            CAT_ESTRUCTURA, "Estructura Sintáctica (Falta de Actor)",
            "No se identifica la entidad responsable de ejecutar la acción.",
            "Iniciar el enunciado con el sujeto (por ejemplo 'El sistema…' o 'El usuario…').",
            "Mal: «Deberá enviar un correo de confirmación al registrarse» -> "
            "Mejor: «El sistema deberá enviar un correo de confirmación al registrarse»."))
    elif not actor_en_sujeto:
        res.append(_obs(
            CAT_ESTRUCTURA, "Estructura Sintáctica (El actor no es el sujeto)",
            "Se menciona un actor, pero no aparece como sujeto de la oración "
            "(posible voz pasiva o construcción impersonal).",
            "Redactar en voz activa, con el actor como sujeto de la acción.",
            "Mal: «Se deberá permitir al usuario cambiar la clave» -> "
            "Mejor: «El sistema deberá permitir al usuario cambiar la clave»."))

    # Modales y verbo de acción
    modales = [(t, _clasificar_modal(t)) for t in doc]
    modales = [(t, c) for t, c in modales if c]
    debiles = [t.text for t, c in modales if c == "debil"]
    hay_fuerte = any(c == "fuerte" for _, c in modales)

    if debiles and not hay_fuerte:
        res.append(_obs(
            CAT_ESTRUCTURA, "Estructura Sintáctica (Verbo Modal Débil)",
            f"Utiliza verbos condicionales o débiles: [b]{', '.join(sorted(set(debiles)))}[/b].",
            "La norma exige el verbo de obligación formal: 'El sistema [b]deberá[/b]…'.",
            "Mal: «El sistema debería guardar los datos» -> Mejor: «El sistema deberá guardar los datos»."))
    elif not hay_fuerte:
        res.append(_obs(
            CAT_ESTRUCTURA, "Estructura Sintáctica (Ausencia de Verbo Obligatorio)",
            "No se encuentra el verbo de obligación 'deberá' que establece qué debe cumplir el sistema.",
            "Incluir 'deberá' seguido de un verbo en infinitivo.",
            "Mal: «El sistema guarda los datos del cliente» -> Mejor: «El sistema deberá guardar los datos del cliente»."))

    acciones = [t for t in doc
                if t.pos_ == "VERB" and "Inf" in t.morph.get("VerbForm")
                and _lema(t) not in ("deber", "poder")]

    if hay_fuerte and not acciones:
        res.append(_obs(
            CAT_ESTRUCTURA, "Estructura Sintáctica (Falta verbo de acción)",
            "Se usa 'deberá', pero no se detecta un verbo en infinitivo que indique qué acción realiza el sistema.",
            "Completar con el verbo que expresa la capacidad requerida.",
            "Mal: «El sistema deberá la lista de productos» -> "
            "Mejor: «El sistema deberá mostrar la lista de productos»."))
    elif acciones and all(not ({c.dep_ for c in v.children} & DEPS_COMPLEMENTO) for v in acciones):
        res.append(_obs(
            CAT_CALIDAD, "Característica 'Completo' (Posible falta de objeto o condición)",
            f"El verbo [b]{acciones[0].text}[/b] no tiene objeto ni complemento asociado: "
            "no queda claro sobre qué actúa el sistema.",
            "Indicar el objeto de la acción y, si corresponde, la condición o restricción.",
            "Mal: «El sistema deberá notificar» -> "
            "Mejor: «El sistema deberá notificar al docente cuando un estudiante entregue una tarea»."))

    # ---- 2. CARACTERÍSTICAS DE CALIDAD ------------------------------------

    # A. Sin ambigüedad 
    ambiguas = []
    for t in doc:
        if t.is_punct:
            continue
        if _forma(t) in TERMINOS_AMBIGUOS or _lema(t) in TERMINOS_AMBIGUOS:
            ambiguas.append(t.text)
    for patron in FRASES_AMBIGUAS:
        m = re.search(rf"\b{patron}\b", texto_norm)
        if m:
            ambiguas.append(m.group(0))
    if ambiguas:
        res.append(_obs(
            CAT_CALIDAD, "Característica 'Sin Ambigüedad' (Incumplida)",
            f"Contiene términos subjetivos o vagos: [b]{', '.join(dict.fromkeys(ambiguas))}[/b].",
            "Reemplazar por criterios objetivos, medibles y verificables (tiempos, cantidades, porcentajes).",
            "Mal: «El sistema deberá responder rápido» -> "
            "Mejor: «El sistema deberá responder las consultas en un máximo de 2 segundos»."))

    # B. Verificable: términos de calidad sin ningún valor medible
    tiene_numero = any(t.like_num or re.search(r"\d", t.text) for t in doc)
    if ambiguas and not tiene_numero:
        res.append(_obs(
            CAT_CALIDAD, "Característica 'Verificable' (Sin valor medible)",
            "El requisito expresa un atributo de calidad pero no incluye ningún número, "
            "unidad o umbral que permita comprobarlo.",
            "Agregar un criterio de aceptación cuantificable que pueda verificarse con una prueba.",
            "Mal: «El sistema deberá ser eficiente» -> "
            "Mejor: «El sistema deberá soportar 200 usuarios concurrentes sin superar 3 segundos de respuesta»."))

    # C. Singular / atómico: verbos coordinados detectados por dependencias
    verbos_conj = [t for t in doc
                   if t.pos_ == "VERB" and t.dep_ == "conj" and t.head.pos_ in ("VERB", "AUX")]
    hay_conector = re.search(CONECTORES_COMPUESTOS, texto_norm) and len(acciones) >= 2
    if verbos_conj or hay_conector:
        if verbos_conj:
            pares = ", ".join(f"{v.head.text} / {v.text}" for v in verbos_conj)
            detalle = f"Se coordinan acciones distintas: [b]{pares}[/b]."
        else:
            detalle = "Se encadenan varias acciones mediante conectores (además, luego, así como…)."
        res.append(_obs(
            CAT_CALIDAD, "Característica 'Singular' (Requisito Compuesto Detectado)",
            detalle,
            "Dividir en requisitos atómicos: cada uno debe expresar una sola capacidad.",
            "Mal: «El sistema deberá registrar el pedido y enviar la factura» -> Mejor: "
            "(1) «El sistema deberá registrar el pedido» y (2) «El sistema deberá enviar la factura»."))

    # D. Consistencia terminológica 
    lemas = {_lema(t) for t in doc}
    for grupo, descripcion in GRUPOS_SINONIMOS:
        usados = sorted(grupo & lemas)
        if len(usados) > 1:
            res.append(_obs(
                CAT_CALIDAD, "Característica 'Consistente' (Terminología alternada)",
                f"Se usan [b]{' y '.join(usados)}[/b] para referirse a {descripcion}.",
                "Elegir un único término y mantenerlo en todo el documento.",
                "Mal: «El sistema deberá avisar al cliente; el usuario podrá…» -> usar siempre el mismo rol."))

    # ---- 3. CRITERIOS LINGÜÍSTICOS ----------------------------------------

    # E. Negación: 'no' que modifica a un verbo
    negaciones = [t.text for t in doc
                  if (_forma(t) == "no" and t.head.pos_ in ("VERB", "AUX"))
                  or _forma(t) in ("nunca", "jamas")]
    if negaciones:
        res.append(_obs(
            CAT_LINGUISTICOS, "Formulación Negativa",
            "La norma recomienda afirmaciones positivas en lugar de restricciones negativas.",
            "Reformular indicando qué debe hacer el sistema en lugar de lo que no debe hacer.",
            "Mal: «El sistema no deberá permitir contraseñas cortas» -> "
            "Mejor: «El sistema deberá exigir contraseñas de al menos 8 caracteres»."))

    # F. Redundancia ('capaz de', 'capacidad de')
    m = re.search(FRASES_REDUNDANTES, texto_norm)
    if m:
        res.append(_obs(
            CAT_LINGUISTICOS, "Redundancia Estructural",
            f"Se detecta la expresión [b]'{m.group(0)}'[/b], que agrega palabras sin aportar significado.",
            "Conectar directamente el sujeto con el verbo de acción.",
            "Mal: «El sistema deberá ser capaz de exportar reportes» -> "
            "Mejor: «El sistema deberá exportar reportes»."))

    # G. Frases escapatoria y 'y/o', 'etc.'
    escapes = [m.group(0) for p in FRASES_ESCAPATORIA
               if (m := re.search(rf"(?<!\w){p}(?!\w)", texto_norm))]
    if escapes:
        res.append(_obs(
            CAT_LINGUISTICOS, "Frases Escapatoria / Expresiones Abiertas",
            f"Expresiones que dejan el requisito abierto: [b]{', '.join(escapes)}[/b].",
            "Eliminarlas o reemplazarlas por la condición exacta o la lista completa.",
            "Mal: «El sistema deberá notificar por correo y/o SMS» -> "
            "Mejor: «El sistema deberá notificar por correo electrónico»."))

    # H. Pronombres demostrativos usados como pronombre (referencia vaga)
    pronombres = [t.text for t in doc if t.pos_ == "PRON" and _forma(t) in DEMOSTRATIVOS]
    if pronombres:
        res.append(_obs(
            CAT_LINGUISTICOS, "Referencia Ambigua (Pronombre)",
            f"El pronombre [b]{', '.join(pronombres)}[/b] no deja claro a qué elemento se refiere.",
            "Repetir el sustantivo al que se hace referencia.",
            "Mal: «El sistema deberá validar el formulario y guardarlo si esto es correcto» -> "
            "Mejor: «…si los datos del formulario son válidos»."))

    # I. Comparativos y superlativos
    comp = []
    for i, t in enumerate(doc):
        f = _forma(t)
        sig = doc[i + 1] if i + 1 < len(doc) else None
        if f in COMPARATIVOS:
            comp.append(t.text)
        elif f in ("mas", "menos") and sig is not None and sig.pos_ in ("ADJ", "ADV"):
            comp.append(f"{t.text} {sig.text}")
        elif "Abs" in t.morph.get("Degree") or re.search(r"[aeo]?(isim)[oa]s?$", f):
            comp.append(t.text)
    if comp:
        res.append(_obs(
            CAT_LINGUISTICOS, "Comparativos / Superlativos",
            f"Expresiones comparativas sin punto de referencia: [b]{', '.join(dict.fromkeys(comp))}[/b].",
            "Indicar contra qué se compara o dar un valor concreto.",
            "Mal: «El sistema deberá ser más rápido» -> "
            "Mejor: «El sistema deberá responder en menos de 2 segundos»."))

    res.sort(key=lambda o: _ORDEN_CAT[o["categoria"]])  # estable: agrupa por categoría
    return res



if __name__ == "__main__":
    casos = [
        "El sistema deberá permitir al usuario iniciar sesión con correo y contraseña.",
        "El sistema debería ser rápido y fácil de usar.",
        "El sistema deberá registrar el pedido y enviar la factura al cliente.",
        "El sistema deberá establecer una conexión segura con el servidor.",
        "Se deberá notificar por correo y/o SMS cuando corresponda.",
        "El sistema no deberá ser capaz de guardar contraseñas en texto plano.",
        "Login de usuarios",
    ]
    for c in casos:
        print("\n>>", c)
        for o in aplicar_reglas_nlp(c):
            print(f"   [{o['categoria']}] {o['tipo']}")
