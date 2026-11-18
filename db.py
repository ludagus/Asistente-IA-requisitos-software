
import csv
import difflib
import os
import re
import sqlite3
import unicodedata
from datetime import datetime

UMBRAL_REVISION = 0.5   # mismo ID y texto parecido => reformulación del mismo requisito

ESQUEMA = """
CREATE TABLE IF NOT EXISTS estudiante (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo  TEXT NOT NULL UNIQUE COLLATE NOCASE
);
CREATE TABLE IF NOT EXISTS proyecto (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    estudiante_id  INTEGER NOT NULL REFERENCES estudiante(id),
    nombre         TEXT NOT NULL COLLATE NOCASE,
    creado_en      TEXT NOT NULL,
    UNIQUE (estudiante_id, nombre)
);
CREATE TABLE IF NOT EXISTS requisito (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    proyecto_id    INTEGER NOT NULL REFERENCES proyecto(id),
    identificador  TEXT NOT NULL COLLATE NOCASE,
    UNIQUE (proyecto_id, identificador)
);
CREATE TABLE IF NOT EXISTS version (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    requisito_id     INTEGER NOT NULL REFERENCES requisito(id),
    intento          INTEGER NOT NULL,
    texto            TEXT NOT NULL,
    fecha            TEXT NOT NULL,
    n_observaciones  INTEGER NOT NULL,
    UNIQUE (requisito_id, intento)
);
CREATE TABLE IF NOT EXISTS observacion (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id   INTEGER NOT NULL REFERENCES version(id),
    ambito       TEXT NOT NULL,          -- 'requisito' o 'conjunto'
    categoria    TEXT,
    tipo         TEXT,
    explicacion  TEXT,
    sugerencia   TEXT,
    ejemplo      TEXT
);
"""


# ---------------------------------------------------------------------------
# Utilidades de texto
# ---------------------------------------------------------------------------
def _norm(s):
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _similitud(a, b):
    return difflib.SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def _igual(a, b):
    """Mismo texto (ignora solo espacios; las tildes sí cuentan como cambio)."""
    return " ".join(a.split()) == " ".join(b.split())


_RE_MARKUP = re.compile(r"\[/?(?:b|i|color(?:=[^\]]*)?|size(?:=[^\]]*)?)\]")


def quitar_markup(texto):
    return _RE_MARKUP.sub("", texto or "")


def para_pdf(texto):
    """Texto plano compatible con las fuentes base de FPDF (latin-1)."""
    texto = quitar_markup(texto)
    for a, b in (("…", "..."), ("→", "->"), ("–", "-"), ("—", "-"), ("•", "-"),
                 ("“", '"'), ("”", '"'), ("‘", "'"), ("’", "'")):
        texto = texto.replace(a, b)
    return texto.encode("latin-1", "replace").decode("latin-1")


# ---------------------------------------------------------------------------
# Base de datos
# ---------------------------------------------------------------------------
class BaseDatos:
    def __init__(self, ruta):
        self.ruta = ruta
        self.con = sqlite3.connect(ruta)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA foreign_keys = ON")
        self.con.executescript(ESQUEMA)
        self.con.commit()

    def cerrar(self):
        self.con.close()

    # ---- estudiantes y proyectos ------------------------------------------
    def obtener_o_crear_estudiante(self, codigo):
        fila = self.con.execute("SELECT id FROM estudiante WHERE codigo = ?", (codigo,)).fetchone()
        if fila:
            return fila["id"]
        cur = self.con.execute("INSERT INTO estudiante (codigo) VALUES (?)", (codigo,))
        self.con.commit()
        return cur.lastrowid

    def proyectos_de(self, estudiante_id):
        filas = self.con.execute(
            "SELECT nombre FROM proyecto WHERE estudiante_id = ? ORDER BY id", (estudiante_id,)).fetchall()
        return [f["nombre"] for f in filas]

    def abrir_proyecto(self, estudiante_id, nombre):
        """Devuelve (proyecto_id, nombre_guardado, creado)."""
        fila = self.con.execute(
            "SELECT id, nombre FROM proyecto WHERE estudiante_id = ? AND nombre = ?",
            (estudiante_id, nombre)).fetchone()
        if fila:
            return fila["id"], fila["nombre"], False
        cur = self.con.execute(
            "INSERT INTO proyecto (estudiante_id, nombre, creado_en) VALUES (?, ?, ?)",
            (estudiante_id, nombre, datetime.now().isoformat(timespec="seconds")))
        self.con.commit()
        return cur.lastrowid, nombre, True

    # ---- requisitos -------------------------------------------------------
    def _consulta_requisitos(self, proyecto_id, identificador=None):
        sql = """
            SELECT r.id AS req_id, r.identificador AS id,
                   v.id AS version_id, v.texto, v.intento, v.n_observaciones
            FROM requisito r JOIN version v ON v.requisito_id = r.id
            WHERE r.proyecto_id = ?
              AND v.intento = (SELECT MAX(intento) FROM version WHERE requisito_id = r.id)
        """
        params = [proyecto_id]
        if identificador is not None:
            sql += " AND r.identificador = ?"
            params.append(identificador)
        sql += " ORDER BY r.id"
        return [dict(f) for f in self.con.execute(sql, params).fetchall()]

    def requisitos(self, proyecto_id):
        """Última versión de cada requisito. Claves: id, texto, intento, n_observaciones."""
        return self._consulta_requisitos(proyecto_id)

    def buscar_requisito(self, proyecto_id, identificador):
        filas = self._consulta_requisitos(proyecto_id, identificador)
        return filas[0] if filas else None

    def siguiente_id(self, proyecto_id, prefijo="RF"):
        mayor = 0
        for f in self.con.execute("SELECT identificador FROM requisito WHERE proyecto_id = ?",
                                  (proyecto_id,)).fetchall():
            m = re.fullmatch(rf"{prefijo}-(\d+)", f["identificador"], re.I)
            if m:
                mayor = max(mayor, int(m.group(1)))
        return f"{prefijo}-{mayor + 1:02d}"

    def resolver_identificador(self, proyecto_id, id_escrito, texto):
        """Decide a qué requisito corresponde el texto analizado.
        Devuelve (identificador, estado, existente) con estado en:
          'nuevo'     : ID escrito que todavía no existe
          'version'   : nueva versión de un requisito existente
          'asignado'  : no traía ID; se le asignó el siguiente libre
          'conflicto' : el ID ya pertenece a OTRO requisito (texto muy distinto)
        """
        if id_escrito:
            existente = self.buscar_requisito(proyecto_id, id_escrito)
            if existente is None:
                return id_escrito, "nuevo", None
            if _similitud(existente["texto"], texto) >= UMBRAL_REVISION:
                return existente["id"], "version", None
            return existente["id"], "conflicto", existente
        for ex in self.requisitos(proyecto_id):
            if _igual(ex["texto"], texto):
                return ex["id"], "version", None      # mismo enunciado analizado otra vez
        return self.siguiente_id(proyecto_id), "asignado", None

    # ---- versiones y observaciones ---------------------------------------
    def guardar_version(self, proyecto_id, identificador, texto, observaciones):
        """Guarda un intento. Devuelve {version_id, intento, nueva}.
        Si el texto no cambió respecto del último intento, no crea otra versión."""
        fila = self.con.execute(
            "SELECT id FROM requisito WHERE proyecto_id = ? AND identificador = ?",
            (proyecto_id, identificador)).fetchone()
        if fila is None:
            cur = self.con.execute(
                "INSERT INTO requisito (proyecto_id, identificador) VALUES (?, ?)",
                (proyecto_id, identificador))
            req_id = cur.lastrowid
        else:
            req_id = fila["id"]

        ultima = self.con.execute(
            "SELECT id, intento, texto FROM version WHERE requisito_id = ? ORDER BY intento DESC LIMIT 1",
            (req_id,)).fetchone()
        if ultima and _igual(ultima["texto"], texto):
            self.con.commit()
            return {"version_id": ultima["id"], "intento": ultima["intento"], "nueva": False}

        intento = (ultima["intento"] if ultima else 0) + 1
        cur = self.con.execute(
            "INSERT INTO version (requisito_id, intento, texto, fecha, n_observaciones) "
            "VALUES (?, ?, ?, ?, ?)",
            (req_id, intento, texto, datetime.now().isoformat(timespec="seconds"), len(observaciones)))
        version_id = cur.lastrowid
        self._insertar_observaciones(version_id, "requisito", observaciones)
        self.con.commit()
        return {"version_id": version_id, "intento": intento, "nueva": True}

    def _insertar_observaciones(self, version_id, ambito, observaciones):
        self.con.executemany(
            "INSERT INTO observacion (version_id, ambito, categoria, tipo, explicacion, sugerencia, ejemplo) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(version_id, ambito, o["categoria"], o["tipo"], o["explicacion"],
              o["sugerencia"], o.get("ejemplo")) for o in observaciones])

    def guardar_observaciones(self, version_id, ambito, observaciones):
        self._insertar_observaciones(version_id, ambito, observaciones)
        self.con.commit()

    def detalle_proyecto(self, proyecto_id):
        """Requisitos con su evolución y las observaciones de su última versión."""
        res = []
        for r in self._consulta_requisitos(proyecto_id):
            vers = self.con.execute(
                "SELECT n_observaciones FROM version WHERE requisito_id = ? ORDER BY intento",
                (r["req_id"],)).fetchall()
            obs = self.con.execute(
                "SELECT categoria, tipo, explicacion, sugerencia, ejemplo FROM observacion "
                "WHERE version_id = ? AND ambito = 'requisito' ORDER BY id",
                (r["version_id"],)).fetchall()
            r["evolucion"] = [v["n_observaciones"] for v in vers]
            r["observaciones"] = [dict(o) for o in obs]
            res.append(r)
        return res

    # ---- exportación para investigación ----------------------------------
    def exportar_csv(self, carpeta, prefijo):
        """Exporta toda la base a dos CSV (versiones y observaciones). Devuelve las rutas."""
        base = """
            FROM version v
            JOIN requisito r ON r.id = v.requisito_id
            JOIN proyecto p ON p.id = r.proyecto_id
            JOIN estudiante e ON e.id = p.estudiante_id
        """
        versiones = self.con.execute(f"""
            SELECT e.codigo AS estudiante, p.nombre AS proyecto, r.identificador,
                   v.intento, v.fecha, v.texto, v.n_observaciones,
                   (SELECT group_concat(o.tipo, ' | ') FROM observacion o
                    WHERE o.version_id = v.id AND o.ambito = 'requisito') AS reglas_incumplidas
            {base} ORDER BY e.codigo, p.nombre, r.identificador, v.intento
        """).fetchall()
        observaciones = self.con.execute(f"""
            SELECT e.codigo AS estudiante, p.nombre AS proyecto, r.identificador, v.intento,
                   o.ambito, o.categoria, o.tipo, o.explicacion
            {base} JOIN observacion o ON o.version_id = v.id
            ORDER BY e.codigo, p.nombre, r.identificador, v.intento, o.id
        """).fetchall()

        ruta_v = os.path.join(carpeta, f"{prefijo}_versiones.csv")
        ruta_o = os.path.join(carpeta, f"{prefijo}_observaciones.csv")
        for ruta, filas, limpiar in ((ruta_v, versiones, ("reglas_incumplidas",)),
                                     (ruta_o, observaciones, ("explicacion",))):
            with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                columnas = filas[0].keys() if filas else []
                w.writerow(columnas)
                for fila in filas:
                    w.writerow([quitar_markup(fila[c]) if c in limpiar else fila[c] for c in columnas])
        return ruta_v, ruta_o
