
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

from motor_nlp import aplicar_reglas_nlp, precargar_modelo


class AsistenteApp(MDApp):
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.historial_analisis = []
        self.dialogo = None

    def build(self):
        self.theme_cls.primary_palette = "LightBlue"
        self.theme_cls.theme_style = "Light"
        try:
            precargar_modelo()
        except RuntimeError:
            pass  # el error se informa al analizar
        
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
        
        try:
            observaciones = aplicar_reglas_nlp(texto_usuario)
        except RuntimeError as e:
            self.root.ids.resultado.text = f"[color=D32F2F]{e}[/color]"
            return
        
        if observaciones:
            salida_pantalla += "[b][color=4B5563]ANÁLISIS PEDAGÓGICO SEGÚN ISO/IEC/IEEE 29148:[/color][/b]\n\n"
            salida_historial += "ESTADO: OBSERVACIONES ENCONTRADAS\n"
            
            
            cat_actual = ""
            for obs in observaciones:
                if obs["categoria"] != cat_actual:
                    cat_actual = obs["categoria"]
                    salida_pantalla += f"[b][color=1976D2]>> {cat_actual}[/color][/b]\n"
                
                salida_pantalla += f"  • [b]{obs['tipo']}:[/b] {obs['explicacion']}\n"
                salida_pantalla += f"    [color=757575][i]Sugerencia: {obs['sugerencia']}[/i][/color]\n"
                if obs.get("ejemplo"):
                    salida_pantalla += f"    [color=757575]Ejemplo: {obs['ejemplo']}[/color]\n"
                salida_pantalla += "\n"
                salida_historial += f"[{obs['categoria']}] {obs['tipo']}: {obs['explicacion']}\n"
                salida_historial += f"  Sugerencia: {obs['sugerencia']}\n"
                if obs.get("ejemplo"):
                    salida_historial += f"  Ejemplo: {obs['ejemplo']}\n"
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
        
        
        if nombre_pestaña == "analisis":
            titulo = "Análisis"
        elif nombre_pestaña == "criterios":
            titulo = "Criterios"
        elif nombre_pestaña == "ayuda":
            titulo = "Ayuda"
        else:
            return
        
        
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
            "[b]Directora:[/b] Mgter. Elizabet Alejandra Matoso\n"
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