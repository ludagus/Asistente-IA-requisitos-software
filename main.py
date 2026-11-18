
import sys
import os
import re
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

from kivy.utils import escape_markup

from motor_nlp import analizar_requisito, analizar_conjunto, precargar_modelo
from db import BaseDatos, para_pdf


# El motor de análisis (spaCy + reglas heurísticas) vive en motor_nlp.py


# APLICACIÓN PRINCIPAL KIVYMD
class AsistenteApp(MDApp):
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.db = None                # BaseDatos (se abre en build)
        self.proyecto_actual = None   # {'id', 'nombre', 'codigo'}
        self.dialogo = None

    def build(self):
        self.theme_cls.primary_palette = "LightBlue"
        self.theme_cls.theme_style = "Light"
        os.makedirs(self.user_data_dir, exist_ok=True)
        self.db = BaseDatos(os.path.join(self.user_data_dir, "asistente.db"))
        try:
            precargar_modelo()
        except RuntimeError:
            pass  # el error se informa al analizar
        
        ruta_kv = os.path.join(os.path.dirname(__file__), "asistente.kv")
        with open(ruta_kv, "r", encoding="utf-8") as f:
            return Builder.load_string(f.read())

    # ------------------------------------------------------------------
    # PROYECTO
    # ------------------------------------------------------------------
    def abrir_proyecto(self):
        codigo = self.root.ids.codigo_input.text.strip().upper()
        nombre = self.root.ids.proyecto_input.text.strip()

        if not re.fullmatch(r"[A-Z0-9_\-]{2,20}", codigo):
            self.mostrar_mensaje(
                "Código no válido",
                "Ingresá un código anónimo de 2 a 20 caracteres (letras, números o guion), "
                "por ejemplo E-017. No uses tu nombre.")
            return

        est_id = self.db.obtener_o_crear_estudiante(codigo)
        if not nombre:
            existentes = self.db.proyectos_de(est_id)
            if existentes:
                lista = "\n".join(f"• {escape_markup(n)}" for n in existentes)
                self.root.ids.estado_proyecto.text = (
                    f"[b]Proyectos de {escape_markup(codigo)}:[/b]\n{lista}\n\n"
                    "[i]Escribí el nombre de uno para abrirlo, o uno nuevo para crearlo.[/i]")
            else:
                self.root.ids.estado_proyecto.text = (
                    f"[i]{escape_markup(codigo)} todavía no tiene proyectos. "
                    "Escribí un nombre para crear el primero.[/i]")
            return

        pid, nombre_guardado, creado = self.db.abrir_proyecto(est_id, nombre)
        self.proyecto_actual = {"id": pid, "nombre": nombre_guardado, "codigo": codigo}
        self.root.ids.resultado.text = ""
        self.refrescar_proyecto("Proyecto creado." if creado else "Proyecto abierto.")

    def refrescar_proyecto(self, aviso=""):
        p = self.proyecto_actual
        if not p:
            return
        reqs = self.db.requisitos(p["id"])
        txt = f"[color=388E3C]{aviso}[/color]\n\n" if aviso else ""
        txt += (f"[b]Proyecto:[/b] {escape_markup(p['nombre'])}    "
                f"[b]Estudiante:[/b] {escape_markup(p['codigo'])}\n\n")
        if not reqs:
            txt += "[i]Todavía no hay requisitos. Analizá el primero en la pestaña 'Análisis'.[/i]"
        else:
            txt += f"[b]Requisitos del proyecto ({len(reqs)}):[/b]\n\n"
            for r in reqs:
                estado = ("sin observaciones" if r["n_observaciones"] == 0
                          else f"{r['n_observaciones']} observaciones")
                extracto = r["texto"] if len(r["texto"]) <= 70 else r["texto"][:67] + "..."
                txt += (f"• [b]{escape_markup(r['id'])}[/b] | "
                        f"intento {r['intento']} | {estado}\n"
                        f"   [color=757575]{escape_markup(extracto)}[/color]\n")
        self.root.ids.estado_proyecto.text = txt

    # ------------------------------------------------------------------
    # ANÁLISIS
    # ------------------------------------------------------------------
    def _formatear_obs(self, observaciones):
        pantalla, cat_actual = "", ""
        for obs in observaciones:
            if obs["categoria"] != cat_actual:
                cat_actual = obs["categoria"]
                pantalla += f"[b][color=1976D2]>> {cat_actual}[/color][/b]\n"
            pantalla += f"  • [b]{obs['tipo']}:[/b] {obs['explicacion']}\n"
            pantalla += f"    [color=757575][i]Sugerencia: {obs['sugerencia']}[/i][/color]\n"
            if obs.get("ejemplo"):
                pantalla += f"    [color=757575]Ejemplo: {obs['ejemplo']}[/color]\n"
            pantalla += "\n"
        return pantalla

    def analizar_texto(self):
        if not self.proyecto_actual:
            self.root.ids.resultado.text = (
                "[i][color=D97706]Primero abrí o creá un proyecto en la pestaña 'Proyecto'.[/color][/i]")
            return

        texto_usuario = self.root.ids.texto_input.text.strip()
        if not texto_usuario:
            self.root.ids.resultado.text = "[i][color=D97706]Por favor, ingresá un requerimiento para analizar.[/color][/i]"
            return

        try:
            r = analizar_requisito(texto_usuario)
        except RuntimeError as e:
            self.root.ids.resultado.text = f"[color=D32F2F]{e}[/color]"
            return

        pid = self.proyecto_actual["id"]
        ident, estado, existente = self.db.resolver_identificador(pid, r["id"], r["texto"])
        observaciones = r["observaciones"]
        pantalla = ""
        guardado = None

        if estado == "conflicto":
            siguiente = self.db.siguiente_id(pid)
            pantalla += (
                f"[b][color=D32F2F]IDENTIFICADOR REPETIDO:[/color][/b] [b]{ident}[/b] ya corresponde a otro "
                f"requisito del proyecto: «{escape_markup(existente['texto'])}»\n"
                f"Si es otro requisito, usá un identificador libre, por ejemplo [b]{siguiente}[/b]. "
                "Si querés reformular el anterior, conservá su idea. "
                "[b]Este intento no se guardó.[/b]\n\n")
        else:
            guardado = self.db.guardar_version(pid, ident, r["texto"], observaciones)
            pantalla += (f"[color=757575]Identificador: {ident}  |  "
                         f"Intento n.º {guardado['intento']}[/color]\n")
            if estado == "asignado":
                pantalla += (f"[color=757575]No indicaste identificador: se le asignó [b]{ident}[/b]. "
                             "Para reformular este requisito, escribilo con ese mismo identificador.[/color]\n")
            if not guardado["nueva"]:
                pantalla += ("[color=757575]El texto no cambió desde el último intento, "
                             "por eso no se registró una nueva versión.[/color]\n")
            pantalla += "\n"

        if observaciones:
            pantalla += "[b][color=4B5563]ANÁLISIS PEDAGÓGICO SEGÚN ISO/IEC/IEEE 29148:[/color][/b]\n\n"
            pantalla += self._formatear_obs(observaciones)
        else:
            pantalla += "[b][color=388E3C]ESTADO GENERAL: SIN OBSERVACIONES[/color][/b]\n\n"
            pantalla += ("[size=15]No se detectaron observaciones con las reglas actuales del asistente "
                         "(Estructura, Características de Calidad y Criterios Lingüísticos de la "
                         "ISO/IEC/IEEE 29148).[/size]\n\n")

        # Consistencia entre todos los requisitos del proyecto
        if guardado:
            reqs = self.db.requisitos(pid)
            n = len(reqs)
            if n >= 2:
                conjunto = analizar_conjunto(reqs)
                if guardado["nueva"]:
                    self.db.guardar_observaciones(guardado["version_id"], "conjunto", conjunto)
                pantalla += f"[b][color=4B5563]ANÁLISIS DEL CONJUNTO ({n} requisitos en el proyecto):[/color][/b]\n\n"
                if conjunto:
                    pantalla += self._formatear_obs(conjunto)
                else:
                    pantalla += (f"[color=388E3C]No se detectaron repeticiones ni inconsistencias entre los "
                                 f"{n} requisitos con las reglas actuales.[/color]\n")
            else:
                pantalla += ("[i][color=757575]Cargá más requisitos en este proyecto para verificar "
                             "la consistencia entre ellos.[/color][/i]\n")
            self.refrescar_proyecto()

        self.root.ids.resultado.text = pantalla

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
        elif nombre_pestaña == "proyecto":
            titulo = "Proyecto"
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
        self.stop()

    def on_stop(self):
        if self.db:
            self.db.cerrar()

    def exportar_analisis(self):
        """PDF del proyecto abierto (para el estudiante)."""
        if not self.proyecto_actual:
            self.mostrar_mensaje("Atención", "Abrí un proyecto en la pestaña 'Proyecto' para exportarlo.")
            return
        p = self.proyecto_actual
        detalle = self.db.detalle_proyecto(p["id"])
        if not detalle:
            self.mostrar_mensaje("Atención", "Este proyecto todavía no tiene requisitos analizados.")
            return

        pdf = FPDF()
        pdf.set_auto_page_break(True, 15)
        pdf.add_page()

        def parrafo(texto, estilo="", tam=10, alto=5.5):
            pdf.set_font("Helvetica", estilo, tam)
            pdf.multi_cell(0, alto, para_pdf(texto), new_x="LMARGIN", new_y="NEXT")

        pdf.set_font("Helvetica", "B", 15)
        pdf.cell(0, 10, para_pdf("Reporte de Proyecto - Asistente de Requisitos"),
                 new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.ln(4)
        parrafo(f"Estudiante: {p['codigo']}    Proyecto: {p['nombre']}", "B", 11)
        parrafo(f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}    "
                f"Norma de referencia: ISO/IEC/IEEE 29148")

        for r in detalle:
            pdf.ln(3)
            parrafo(f"{r['id']}  |  Intentos: {r['intento']}", "B", 11)
            parrafo(f"Texto actual: {r['texto']}")
            if len(r["evolucion"]) > 1:
                parrafo("Observaciones por intento: " + " -> ".join(str(x) for x in r["evolucion"]))
            if r["observaciones"]:
                parrafo("Observaciones pendientes:", "B")
                for o in r["observaciones"]:
                    parrafo(f"- [{o['categoria']}] {o['tipo']}: {o['explicacion']}")
                    parrafo(f"   Sugerencia: {o['sugerencia']}", "I")
                    if o["ejemplo"]:
                        parrafo(f"   Ejemplo: {o['ejemplo']}", "I")
            else:
                parrafo("Sin observaciones con las reglas actuales.")

        try:
            conjunto = analizar_conjunto(self.db.requisitos(p["id"]))
        except RuntimeError:
            conjunto = []
        pdf.ln(4)
        parrafo("Consistencia entre requisitos del proyecto", "B", 12)
        if conjunto:
            for o in conjunto:
                parrafo(f"- {o['tipo']}: {o['explicacion']}")
                parrafo(f"   Sugerencia: {o['sugerencia']}", "I")
        else:
            parrafo("No se detectaron repeticiones ni inconsistencias con las reglas actuales.")

        nombre_seguro = re.sub(r"\W+", "_", p["nombre"])
        nombre_pdf = f"reporte_{p['codigo']}_{nombre_seguro}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        try:
            pdf.output(nombre_pdf)
            self.mostrar_mensaje("Éxito", f"Reporte guardado con éxito:\n{os.path.abspath(nombre_pdf)}")
        except Exception as e:
            self.mostrar_mensaje("Error", f"No se pudo crear el PDF: {str(e)}")

    def exportar_csv(self):
        """CSV con todos los datos de la base (para la investigación)."""
        prefijo = f"datos_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        try:
            ruta_v, ruta_o = self.db.exportar_csv(os.getcwd(), prefijo)
            self.mostrar_mensaje(
                "Datos exportados",
                f"Se generaron:\n{ruta_v}\n{ruta_o}\n\nBase de datos:\n{self.db.ruta}")
        except Exception as e:
            self.mostrar_mensaje("Error", f"No se pudo exportar: {str(e)}")

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