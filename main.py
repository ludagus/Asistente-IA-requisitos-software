from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton
from kivy.lang import Builder
from kivymd.app import MDApp
from kivymd.uix.tab import MDTabsBase
from kivymd.uix.boxlayout import MDBoxLayout
from kivy.core.window import Window
from analizador import analizar_requisito
from datetime import datetime
import re

Window.size = (900, 600)

class Tab(MDBoxLayout, MDTabsBase):
    pass

class AsistenteApp(MDApp):
# Agregamos el constructor para asegurar que la lista exista siempre
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.historial_analisis = [] # Aquí se crea la lista apenas arranca la app

    def build(self):
        # Tu lógica de carga de archivo .kv
        return Builder.load_file("asistente.kv")
    
    def abrir_menu(self):
        self.root.ids.nav_drawer.set_state("toggle")

        self.historial_analisis = [] # <-- NUEVO: Lista para guardar la sesión
        return Builder.load_file("asistente.kv")

    def analizar_texto(self):
        texto = self.root.ids.texto_input.text.strip()
        if not texto:
            self.root.ids.resultado.text = "[i]Por favor, ingresá un texto...[/i]"
            return

        resultados = analizar_requisito(texto)
        
        # Formatear salida para la pantalla
        salida_pantalla = ""
        # Guardaremos una versión limpia para el PDF
        salida_historial = f"REQUERIMIENTO: {texto}\n"
        
        for r in resultados:
            salida_pantalla += f"[b]{r['tipo']}[/b]\n"
            salida_pantalla += f"[size=14]{r['explicacion']}[/size]\n"
            salida_pantalla += f"[color=666666][i]Sugerencia: {r['sugerencia']}[/i][/color]\n\n"
            
            # Versión para el historial (sin etiquetas de color de Kivy)
            salida_historial += f"- {r['tipo']}: {r['explicacion']} -> Sugerencia: {r['sugerencia']}\n"
        
        salida_historial += "\n" + "="*40 + "\n\n"
        
        # AGREGAR AL HISTORIAL DE LA SESIÓN
        self.historial_analisis.append(salida_historial)
        
        self.root.ids.resultado.text = salida_pantalla

    def exportar_analisis(self):
        if not self.historial_analisis:
            self.mostrar_mensaje("Error", "No hay análisis en esta sesión para exportar.")
            return

        from fpdf import FPDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, "Reporte de Sesión - Análisis de Requisitos", ln=True, align='C')
        pdf.ln(10)
        
        pdf.set_font("Arial", size=10)
        pdf.cell(0, 10, f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)
        pdf.cell(0, 10, "Autora: Laura Pared", ln=True)
        pdf.ln(5)

        # RECORRER TODO EL HISTORIAL
        pdf.set_font("Arial", size=11)
        for bloque in self.historial_analisis:
            # multi_cell maneja automáticamente los saltos de línea largos
            pdf.multi_cell(0, 8, bloque)
        
        pdf.ln(10)
        pdf.set_font("Arial", 'I', 8)
        pdf.cell(0, 10, "Fin del reporte de sesión.", align='C')

        fecha_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_archivo = f"sesion_{fecha_str}.pdf"
        
        try:
            pdf.output(nombre_archivo)
            self.mostrar_mensaje("Éxito", f"Se exportaron {len(self.historial_analisis)} análisis a {nombre_archivo}")
        except Exception as e:
            self.mostrar_mensaje("Error", f"Error al crear PDF: {str(e)}")

    def navegar(self, tab_name):
# 1. Obtenemos la lista de todas las pestañas
        tabs_list = self.root.ids.tabs.get_slides()
        
        # 2. Buscamos el índice de la pestaña que coincida con el nombre
        indice_destino = -1
        for i, tab in enumerate(tabs_list):
            if tab.name == tab_name:
                indice_destino = i
                break
        
        # 3. Si encontramos el índice, cambiamos la pestaña
        if indice_destino != -1:
            # Usamos el carrusel interno para cambiar de diapositiva directamente
            self.root.ids.tabs.carousel.load_slide(tabs_list[indice_destino])
        
        # 4. Cerramos el menú lateral
        self.root.ids.nav_drawer.set_state("close")
        
    def limpiar(self):
        self.root.ids.texto_input.text = ""
        self.root.ids.resultado.text = ""



    def mostrar_mensaje(self, titulo, mensaje):
        dialog = MDDialog(
            title=titulo,
            text=mensaje,
            buttons=[MDFlatButton(text="OK", on_release=lambda x: dialog.dismiss())],
        )
        dialog.open()

    def mostrar_acerca_de(self):
        dialog = MDDialog(
            title="Acerca del Asistente",
            text="Autora: Laura Pared\nInstitución: ISFD Nº XX",
            buttons=[MDFlatButton(text="Cerrar", on_release=lambda x: dialog.dismiss())],
        )
        dialog.open()

    def salir(self):
        """Cierra la aplicación de forma limpia"""
        self.stop() # Este método de MDApp cierra la ventana y detiene los hilos correctamente

if __name__ == "__main__":
    AsistenteApp().run()
