# analizador.py
import json
import re
import unicodedata
import os

# Carga global para no leer el disco en cada análisis
CRITERIOS = {}

def cargar_criterios():
    global CRITERIOS
    if not CRITERIOS:
        ruta = "criterios.json"
        if os.path.exists(ruta):
            with open(ruta, "r", encoding="utf-8") as f:
                CRITERIOS = json.load(f)
        else:
            # Fallback por si el archivo no existe
            CRITERIOS = {"ambiguas": [], "incompletos": [], "contradictorios": []}
    return CRITERIOS

def normalizar_texto(texto):
    texto = texto.lower()
    texto = unicodedata.normalize('NFKD', texto)
    texto = ''.join([c for c in texto if not unicodedata.combining(c)])
    texto = re.sub(r'[^a-z0-9\s]', ' ', texto)
    return re.sub(r'\s+', ' ', texto).strip()

def analizar_requisito(texto):
    criterios = cargar_criterios()
    texto_norm = normalizar_texto(texto)
    palabras = set(texto_norm.split()) # Uso de set para búsqueda O(1)
    feedback = []

    # 1) Ambigüedad (Naranja)
    ambig_list = [normalizar_texto(w) for w in criterios.get("ambiguas", [])]
    for amb in ambig_list:
        if amb in palabras:
            feedback.append({
                "tipo": "[color=FFA500]AMBIGÜEDAD[/color]",
                "explicacion": f"El término '{amb}' es subjetivo.",
                "sugerencia": f"Reemplazalo por una métrica cuantificable."
            })

    # 2) Estructura/Incompletitud (Rojo)
    verbos_ok = [normalizar_texto(v) for v in criterios.get("incompletos", [])]
    if not any(v in palabras for v in verbos_ok):
        feedback.append({
            "tipo": "[color=FF0000]ESTRUCTURA[/color]",
            "explicacion": "Falta el verbo de obligatoriedad.",
            "sugerencia": "Usá siempre 'El sistema debe...' para normalizar el requisito."
        })

    # 3) Inconsistencia (Púrpura)
    for par in criterios.get("contradictorios", []):
        p0, p1 = normalizar_texto(par[0]), normalizar_texto(par[1])
        if p0 in palabras and p1 in palabras:
            feedback.append({
                "tipo": "[color=800080]INCONSISTENCIA[/color]",
                "explicacion": f"Mezclás '{par[0]}' y '{par[1]}'.",
                "sugerencia": "Elegí un solo término para referirte a la misma entidad."
            })

    if not feedback:
        return [{"tipo": "[color=008000]CORRECTO[/color]", "explicacion": "Cumple con las heurísticas básicas.", "sugerencia": "¡Buen trabajo!"}]
    
    return feedback