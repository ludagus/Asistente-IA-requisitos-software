# analizador.py
import json
import re
import unicodedata

def cargar_criterios():
    with open("criterios.json", "r", encoding="utf-8") as f:
        return json.load(f)

def normalizar_texto(texto):
    """
    - pasa a minúsculas
    - quita tildes/diacríticos
    - reemplaza signos de puntuación por espacios
    """
    texto = texto.lower()
    # quitar tildes
    texto = unicodedata.normalize('NFKD', texto)
    texto = ''.join([c for c in texto if not unicodedata.combining(c)])
    # reemplazar puntuación por espacio (mantiene letras y números)
    texto = re.sub(r'[^a-z0-9\s]', ' ', texto)
    # colapsar espacios múltiples
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto

def tokenizar(texto):
    # devuelve lista de tokens (palabras)
    return re.findall(r'\b[a-z0-9]+\b', texto)

def analizar_requisito(texto):
    criterios = cargar_criterios()

    texto_norm = normalizar_texto(texto)
    palabras = tokenizar(texto_norm)

    feedback = []

    # 1) Detección de ambigüedad (palabras vagas)
    ambig_list = [normalizar_texto(w) for w in criterios.get("ambiguas", [])]
    for amb in ambig_list:
        if amb in palabras:
            feedback.append({
                "tipo": "Ambigüedad",
                "palabra": amb,
                "explicacion": f"El término '{amb}' puede interpretarse de distintas formas según el contexto.",
                "sugerencia": f"Reemplazá '{amb}' por una medida o descripción concreta. Ej.: 'El sistema debe procesar 100 solicitudes por segundo' en lugar de '{amb}'."
            })

    # 2) Detección de incompletitud: buscamos verbos que indiquen acción del requisito
    verbos_esperados = [normalizar_texto(v) for v in criterios.get("incompletos", [])]
    if not any(v in palabras for v in verbos_esperados):
        feedback.append({
            "tipo": "Incompletitud",
            "palabra": "",
            "explicacion": "No se identifica una acción clara en el requisito (verbo esperado: 'debe', 'debería', etc.).",
            "sugerencia": "Comenzá el requisito con 'El sistema debe ...' o 'El usuario podrá ...' para dejar clara la acción esperada."
        })

    # 3) Detección de contradicciones / términos duplicados que pueden ser distintos
    for par in criterios.get("contradictorios", []):
        # normalizar par
        p0 = normalizar_texto(par[0])
        p1 = normalizar_texto(par[1])
        if p0 in palabras and p1 in palabras:
            feedback.append({
                "tipo": "Inconsistencia",
                "palabra": f"{p0} / {p1}",
                "explicacion": f"Se usan '{par[0]}' y '{par[1]}' que podrían referirse a entidades distintas; conviene unificar la denominación.",
                "sugerencia": "Usá una sola denominación para el mismo actor (por ejemplo, 'usuario') a lo largo del documento."
            })

    # Si no se detectó nada, devolvemos correcto
    if not feedback:
        feedback.append({
            "tipo": "Correcto",
            "palabra": "",
            "explicacion": "No se detectaron problemas comunes con la heurística actual.",
            "sugerencia": "Mantener esta claridad y utilizar métricas cuando corresponda."
        })

    return feedback

