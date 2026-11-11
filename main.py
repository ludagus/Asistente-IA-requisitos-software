
import sys
import os
from datetime import datetime

from kivy.factory import Factory
from kivymd.uix.tab import MDTabsBase
try:
    Factory.register('MDTabsBase', cls=MDTabsBase)
except Exception:
    pass

from kivy.lang import Builder
from kivymd.app import MDApp
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton
from fpdf import FPDF
from kivy.core.window import Window

Window.size = (950, 650)


# MOTOR DE REGLAS GRAMATICALES 
def aplicar_reglas_nlp(texto):
    resultados = []
    texto_min = texto.lower()
    palabras = texto_min.split()
    
    # --- 1. ESTRUCTURA Y LONGITUD MÍNIMA ---
    if len(palabras) < 6:
        resultados.append({
            "categoria": "ESTRUCTURA",
            "tipo": "Requisito Incompleto (Longitud Insuficiente)",
            "explicacion": f"La frase es demasiado corta ([b]{len(palabras)} palabras[/b]). No llega a estructurar un componente sintáctico completo.",
            "sugerencia": "Completar la idea siguiendo la estructura formal: Actor + Verbo imperativo + Objeto + Condición/Restricción."
        })
        return resultados 

    # Falta de Actor o Sujeto
    if not any(p in texto_min for p in ["sistema", "aplicación", "software", "usuario", "cliente", "administrador"]):
        resultados.append({
            "categoria": "ESTRUCTURA",
            "tipo": "Estructura Sintáctica (Falta de Actor)",
            "explicacion": "El requisito no identifica explícitamente al actor o entidad responsable de ejecutar la acción.",
            "sugerencia": "Iniciar la redacción indicando claramente el sujeto (ej: 'El sistema...' o 'El usuario...')."
        })

    # Verificación de Verbos de Obligación / Condicionales
    palabras_incompletas = ["debería", "podría", "deberia", "podria", "debe"]
    encontradas_incompletas = [p for p in palabras_incompletas if p in palabras]
    
    if encontradas_incompletas:
        resultados.append({
            "categoria": "ESTRUCTURA",
            "tipo": "Estructura Sintáctica (Verbo Modal Débil)",
            "explicacion": f"Utiliza verbos condicionales o débiles: [b]{', '.join(encontradas_incompletas)}[/b].",
            "sugerencia": "La norma exige utilizar el verbo imperativo de obligación formal: 'El sistema [b]deberá[/b]...'"
        })
    elif not any(v in palabras for v in ["deberá"]):
        resultados.append({
            "categoria": "ESTRUCTURA",
            "tipo": "Estructura Sintáctica (Ausencia de Verbo Obligatorio)",
            "explicacion": "No se encuentra la palabra clave obligatoria 'deberá' para establecer qué acción debe cumplir el sistema.",
            "sugerencia": "Asegurar el uso del verbo imperativo adecuado en la estructura del enunciado."
        })


    # --- 2. CARACTERÍSTICAS DE CALIDAD Y CRITERIOS LINGÜÍSTICOS (ISO/IEC/IEEE 29148) ---

    # A. Característica: Sin ambigüedad
    palabras_ambiguas = [
        "rápido", "eficiente", "fácil", "intuitivo", "intuitiva", "mejorado", "seguro", "flexible", "amigable",
        "cosas", "todos", "todas", "siempre", "nunca", "algunos", "varios", "muchos", "sin errores", "correcto",
        "aproximadamente", "etcétera", "adecuado", "apropiado", "optimizar", "minimizar", "sencilla", "agilizar",
        "maximizar", "estable", "robusto", "potente", "inmediatamente", "inmediato", "inmediata", "rapido", "facil"
    ]
    encontradas_ambiguas = [p for p in palabras_ambiguas if p in texto_min]
    if encontradas_ambiguas:
        resultados.append({
            "categoria": "CARACTERÍSTICAS DE CALIDAD",
            "tipo": "Característica 'Sin Ambigüedad' (Incumplida)",
            "explicacion": f"Contiene términos subjetivos o vagos: [b]{', '.join(encontradas_ambiguas)}[/b].",
            "sugerencia": "Reemplazar por criterios objetivos, medibles y verificables (ej: tiempos en segundos, porcentajes exactos)."
        })
        
    # B. Característica: Singular / Atomicidad (Evitar requisitos compuestos reales)
    # Detecta si hay una conjunción 'y' pero evalúa si separa dos verbos principales (acciones distintas)
    if " y " in texto_min and len(palabras) > 8:
        # Buscamos si la "y" está conectando acciones (verbos) en lugar de una simple lista de datos
        # Una heurística sencilla: si después de la 'y' aparece un verbo de acción claro, es compuesto.
        verbos_accion_compuestos = ["generar", "enviar", "crear", "modificar", "eliminar", "calcular", "mostrar", "imprimir", "validar", "guardar", "actualizar"]
        
        # Obtenemos la parte de la frase posterior a la "y"
        partes_frase = texto_min.split(" y ")
        if len(partes_frase) > 1 and any(v in partes_frase[1] for v in verbos_accion_compuestos):
            resultados.append({
                "categoria": "CARACTERÍSTICAS DE CALIDAD",
                "tipo": "Característica 'Singular' (Requisito Compuesto Detectado)",
                "explicacion": "El enunciado unifica dos acciones independientes mediante la conjunción 'y' (ej. registrar y enviar/generar).",
                "sugerencia": "Dividir el enunciado en dos requisitos atómicos independientes que expresen una sola capacidad cada uno."
            })
    # C. Criterio Lingüístico: Evitar requisitos negativos ("no deberá")
    if "no deberá" in texto_min or "no debe" in texto_min:
        resultados.append({
            "categoria": "CRITERIOS LINGÜÍSTICOS",
            "tipo": "Formulación Negativa Prohibida",
            "explicacion": "La norma establece que deben utilizarse afirmaciones positivas en lugar de restricciones negativas.",
            "sugerencia": "Reformular el requisito expresando qué es lo que el sistema debe hacer en lugar de lo que no debe hacer."
        })

    # D. Criterio Lingüístico: Evitar redundancias ("capaz de")
    if "capaz de" in texto_min:
        resultados.append({
            "categoria": "CRITERIOS LINGÜÍSTICOS",
            "tipo": "Redundancia Estructural ('capaz de')",
            "explicacion": "Se detecta el uso de la frase 'capaz de', desaconsejada por la norma por agregar redundancia innecesaria.",
            "sugerencia": "Eliminar la frase y conectar directamente el sujeto con el verbo de acción (ej: 'El sistema deberá procesar...')."
        })

    # E. Consistencia Terminológica (Actores y Entidad)
    if "usuario" in texto_min and "cliente" in texto_min:
        resultados.append({
            "categoria": "CARACTERÍSTICAS DE CALIDAD",
            "tipo": "Característica 'Consistente' (Conflicto de Actores)",
            "explicacion": "Se detecta el uso alternado de [b]'usuario'[/b] y [b]'cliente'[/b] para referirse al mismo rol.",
            "sugerencia": "Mantener la consistencia terminológica utilizando un único término en todo el documento."
        })
        
    if "sistema" in texto_min and "aplicación" in texto_min:
        resultados.append({
            "categoria": "CARACTERÍSTICAS DE CALIDAD",
            "tipo": "Característica 'Consistente' (Conflicto de Entidad)",
            "explicacion": "Se detecta el uso simultáneo de [b]'sistema'[/b] y [b]'aplicación'[/b] para denominar al software.",
            "sugerencia": "Estandarizar el vocabulario de la tecnología (emplear siempre 'El sistema')."
        })

    return resultados


# APLICACIÓN PRINCIPAL KIVYMD
class AsistenteApp(MDApp):
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.historial_analisis = []
        self.dialogo = None

    def build(self):
        self.theme_cls.primary_palette = "LightBlue"
        self.theme_cls.theme_style = "Light"
        
        ruta_kv = os.path.join(os.path.dirname(__file__), "asistente.kv")
        with open(ruta_kv, "r", encoding="utf-8") as f:
            return Builder.load_string(f.read())

    def analizar_texto(self):
        texto_usuario = self.root.ids.texto_input.text.strip()
        
        if not texto_usuario:
            self.root.ids.resultado.text = "[i][color=D97706]Por favor, ingresá un requerimiento para analizar.[/color][/i]"
            return

        salida_pantalla = ""
        salida_historial = f"REQUERIMIENTO EVALUADO: {texto_usuario}\n"
        salida_historial += f"FECHA/HORA: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
        
        observaciones = aplicar_reglas_nlp(texto_usuario)
        
        if observaciones:
            salida_pantalla += "[b][color=4B5563]ANÁLISIS PEDAGÓGICO SEGÚN ISO/IEC/IEEE 29148:[/color][/b]\n\n"
            salida_historial += "ESTADO: OBSERVACIONES ENCONTRADAS\n"
            
            
            cat_actual = ""
            for obs in observaciones:
                if obs["categoria"] != cat_actual:
                    cat_actual = obs["categoria"]
                    salida_pantalla += f"[b][color=1976D2]>> {cat_actual}[/color][/b]\n"
                
                salida_pantalla += f"  • [b]{obs['tipo']}:[/b] {obs['explicacion']}\n"
                salida_pantalla += f"    [color=757575][i]Sugerencia: {obs['sugerencia']}[/i][/color]\n\n"
                salida_historial += f"[{obs['categoria']}] {obs['tipo']}: {obs['explicacion']}\n"
        else:
            salida_pantalla += "[b][color=388E3C]ESTADO GENERAL: REQUISITO CORRECTO[/color][/b]\n\n"
            salida_pantalla += "[size=15]El requerimiento cumple adecuadamente con los criterios de [b]Estructura[/b] y las [b]Características de Calidad[/b] de la norma ISO/IEC/IEEE 29148.[/size]"
            salida_historial += "ESTADO: CORRECTO\n"

        salida_historial += "\n" + "="*50 + "\n\n"
        self.historial_analisis.append(salida_historial)
        self.root.ids.resultado.text = salida_pantalla

    def navegar(self, nombre_pestaña):
        """Cambia de pestaña utilizando los IDs directos de la interfaz y cierra el menú lateral."""
        tabs_widget = self.root.ids.tabs
        
        # 
        if nombre_pestaña == "analisis":
            titulo = "Análisis"
        elif nombre_pestaña == "criterios":
            titulo = "Criterios"
        elif nombre_pestaña == "ayuda":
            titulo = "Ayuda"
        else:
            return
        
        # Recorremos las pestañas por su texto de etiqueta y cambiamos
        for item in tabs_widget.get_tab_list():
            if item.text == titulo:
                tabs_widget.switch_tab(item)
                break
                
        # Cierra el menú lateral
        self.root.ids.nav_drawer.set_state("close") 

    def abrir_menu(self):
        self.root.ids.nav_drawer.set_state("open")

    def limpiar(self):
        self.root.ids.texto_input.text = ""
        self.root.ids.resultado.text = ""

    def mostrar_acerca_de(self, *args):
        info_tfi = (
            "[b]Asistente Inteligente para el Aprendizaje y Corrección de la Redacción de Requerimientos de Software en Estudiantes en Etapa de Formación[/b]\n\n"
            "[b]Trabajo Final (TFI) - Especialización en Tecnologías de la Información[/b]\n"
            "Facultad de Ciencias Exactas y Naturales y Agrimensura\n"
            "Universidad Nacional del Nordeste (UNNE)\n\n"
            "[b]Autor:[/b] Pared, Laura Rosana\n"
            "[b]Director:[/b] Mgter. Elizabet Alejandra Matoso\n"
            "[b]Co-Director:[/b] Dr. Emanuel Irrazábal\n"
            "[b]Año:[/b] 2026\n\n"
            "[i]Prototipo orientado al análisis pedagógico de requerimientos de software según el estándar ISO/IEC/IEEE 29148.[/i]"
        )
        
        # 
        self.dialog = MDDialog(
            title="Acerca del Trabajo Final",
            text=info_tfi,
            md_bg_color=(0.95, 0.97, 1, 1),  # Fondo azul pastel 
            radius=[16, 16, 16, 16],          # Bordes redondeados elegantes
            buttons=[
                MDFlatButton(
                    text="CERRAR",
                    theme_text_color="Custom",
                    text_color=(0.12, 0.47, 0.75, 1),
                    on_release=lambda x: self.dialog.dismiss()
                ),
            ],
        )
        self.dialog.open()

    def salir(self):
        sys.exit()

    def exportar_analisis(self):
        if not self.historial_analisis:
            self.mostrar_mensaje("Atención", "No hay análisis en esta sesión para exportar.")
            return

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, "Reporte de Sesion - Asistente de Requisitos", ln=True, align='C')
        pdf.ln(10)
        
        pdf.set_font("Arial", size=11)
        for bloque in self.historial_analisis:
            bloque_limpio = bloque.replace("[b]", "").replace("[/b]", "").replace("[color=D32F2F]", "").replace("[/color]", "").replace("[color=1976D2]", "").replace("[color=388E3C]", "").replace("[color=757575]", "").replace("[/color]", "")
            pdf.multi_cell(0, 7, bloque_limpio)
        
        nombre_pdf = f"reporte_sesion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        try:
            pdf.output(nombre_pdf)
            self.mostrar_mensaje("Éxito", f"Reporte guardado con éxito:\n{nombre_pdf}")
        except Exception as e:
            self.mostrar_mensaje("Error", f"No se pudo crear el PDF: {str(e)}")

    def mostrar_mensaje(self, titulo, mensaje):
        if not self.dialogo:
            self.dialogo = MDDialog(
                title=titulo,
                text=mensaje,
                buttons=[MDFlatButton(text="Aceptar", on_release=lambda x: self.dialogo.dismiss())],
            )
        else:
            self.dialogo.title = titulo
            self.dialogo.text = mensaje
        self.dialogo.open()


if __name__ == "__main__":
    AsistenteApp().run()