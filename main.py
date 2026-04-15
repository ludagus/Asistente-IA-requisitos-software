from kivy.lang import Builder
from kivymd.app import MDApp
from kivymd.uix.tab import MDTabsBase
from kivymd.uix.boxlayout import MDBoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.core.window import Window
from analizador import analizar_requisito

# Ajuste de tamaño si ejecutás en PC
Window.size = (900, 600)


class Tab(MDBoxLayout, MDTabsBase):
    """Clase base para pestañas."""


class AsistenteApp(MDApp):
    def build(self):
        self.title = "Asistente Inteligente de Requisitos"
        self.theme_cls.primary_palette = "Blue"
        self.theme_cls.theme_style = "Light"
        return Builder.load_file("asistente.kv")

    def abrir_menu(self):

        """Abre o cierra el panel lateral"""
        try:
            nav_drawer = self.root.ids["nav_drawer"]
        except KeyError:
            # Si no lo encuentra en el nivel raíz, busca dentro del NavigationLayout
            nav_drawer = self.root.children[0].children[0]
        
        if nav_drawer.state == "open":
            nav_drawer.set_state("close")
        else:
            nav_drawer.set_state("open")

    def navegar(self, destino):
        """Muestra una pestaña según el destino elegido en el menú"""
        tabs = self.root.ids.tabs
        nav_drawer = self.root.ids.nav_drawer

        if destino == "analisis":
            tabs.switch_tab("Análisis")
        elif destino == "criterios":
            tabs.switch_tab("Criterios")
        elif destino == "ayuda":
            tabs.switch_tab("Ayuda")

        nav_drawer.set_state("close")

    def analizar_texto(self):
        texto = self.root.ids.texto_input.text.strip()
        if not texto:
            self.root.ids.resultado.text = "[b][color=ff3333]Por favor, ingrese un requerimiento.[/color][/b]"
            return

        resultados = analizar_requisito(texto)
        salida = ""
        for r in resultados:
            if isinstance(r, dict):
                salida += f"[b]Tipo:[/b] {r.get('tipo', 'N/A')}\n"
                salida += f"[b]Palabra:[/b] {r.get('palabra', '---')}\n"
                salida += f"[b]Explicación:[/b] {r.get('explicacion', '')}\n"
                salida += f"[b]Sugerencia:[/b] {r.get('sugerencia', '')}\n\n"
            else:
                salida += str(r) + "\n\n"

        self.root.ids.resultado.text = salida

    def limpiar(self):
        self.root.ids.texto_input.text = ""
        self.root.ids.resultado.text = ""

    def mostrar_acerca_de(self):
        """Muestra una ventana informativa"""
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton

        dialog = MDDialog(
            title="Acerca del Asistente",
            text=(
                "Este prototipo fue desarrollado como parte del Trabajo Final Integrador "
                "de la Especialización en Tecnología de la Información.\n\n"
                "Autora: Laura Pared\n"
                "Institución: ISFD Nº XX\n"
                "Año: 2025"
            ),
            buttons=[
                MDFlatButton(text="Cerrar", on_release=lambda x: dialog.dismiss())
            ],
        )
        dialog.open()

    def salir(self):
        """Cierra la aplicación"""
        import sys
        sys.exit(0)


if __name__ == "__main__":
    AsistenteApp().run()
