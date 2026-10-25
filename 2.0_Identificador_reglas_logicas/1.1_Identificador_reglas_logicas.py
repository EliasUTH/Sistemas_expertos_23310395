import json
import os
import re
import tempfile
import unicodedata
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

ARCHIVO = Path(__file__).resolve().with_name('conocimiento_logico.json')

def normalizar(texto):
    t = unicodedata.normalize('NFD', texto.casefold())
    t = ''.join(c for c in t if unicodedata.category(c) != 'Mn')
    return re.sub(r'\s+', ' ', t).strip(' .,!¡¿?;:')

class AnalizadorRecursivo:
    """Analizador por descenso recursivo. Precedencia: Y > O.

    Gramatica:
        expresion := conjuncion ('o' conjuncion)*
        conjuncion := termino (('y'|'pero') termino)*
        termino := '(' expresion ')' | afirmacion
    """

    def __init__(self, texto):
        self.tokens = re.findall(r'\(|\)|\b(?:y|o|pero)\b|[^()\s]+', texto, flags=re.I)
        self.pos = 0

    def actual(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def operador(self):
        t = self.actual()
        n = normalizar(t) if t else ''
        return n if n in ('y', 'o', 'pero') else None

    def leer(self):
        if not self.tokens:
            raise ValueError('No hay afirmaciones para analizar.')
        nodo = self.disyuncion()
        if self.actual() is not None:
            raise ValueError(f'Elemento inesperado: {self.actual()}')
        return nodo

    def disyuncion(self):
        nodo = self.conjuncion()
        while self.operador() == 'o':
            self.pos += 1
            nodo = ('∨', nodo, self.conjuncion())
        return nodo

    def conjuncion(self):
        nodo = self.termino()
        while self.operador() in ('y', 'pero'):
            self.pos += 1
            nodo = ('∧', nodo, self.termino())
        return nodo

    def termino(self):
        if self.actual() == '(':
            self.pos += 1
            nodo = self.disyuncion()
            if self.actual() != ')':
                raise ValueError('Falta cerrar un paréntesis.')
            self.pos += 1
            return nodo
        palabras = []
        while self.actual() is not None and self.actual() not in ('(', ')') and not self.operador():
            palabras.append(self.actual())
            self.pos += 1
        afirmacion = ' '.join(palabras).strip(' .,!¡¿?;:')
        if not afirmacion:
            raise ValueError('Hay una afirmación incompleta junto a un conector.')
        if self.actual() == '(':
            raise ValueError('Falta un conector antes del paréntesis.')
        return ('atomo', afirmacion)


def representar(nodo, registrar):
    if nodo[0] == 'atomo':
        return registrar(nodo[1])
    _, izq, der = nodo
    return f'({representar(izq, registrar)} {nodo[0]} {representar(der, registrar)})'


class BaseConocimiento:
    def __init__(self, archivo=ARCHIVO):
        self.archivo = Path(archivo)
        self.atomos = []  # {'id': ..., 'texto': ...}
        self.reglas = []  # {'id': ..., 'texto': ..., 'expresion': ...}
        self.cargar()

    def cargar(self):
        if not self.archivo.exists():
            return
        try:
            datos = json.loads(self.archivo.read_text(encoding='utf-8'))
            atomos, reglas = datos['atomos'], datos['reglas']
            if not isinstance(atomos, list) or not isinstance(reglas, list):
                raise ValueError('Estructura inválida')
            for i, a in enumerate(atomos, 1):
                if a['id'] != f'X{i}' or not isinstance(a['texto'], str):
                    raise ValueError('Átomos inválidos')
            for i, r in enumerate(reglas, 1):
                if r['id'] != f'R{i}' or not all(isinstance(r[k], str) for k in ('texto', 'expresion')):
                    raise ValueError('Reglas inválidas')
            if len({normalizar(a['texto']) for a in atomos}) != len(atomos):
                raise ValueError('Átomos duplicados')
            self.atomos, self.reglas = atomos, reglas
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise ValueError(f'No se pudo leer {self.archivo.name}: {exc}') from exc

    def guardar(self):
        self.archivo.parent.mkdir(parents=True, exist_ok=True)
        temporal = None
        try:
            with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=self.archivo.parent,
                                             prefix='.logica_', suffix='.tmp', delete=False) as fh:
                temporal = Path(fh.name)
                json.dump({'atomos': self.atomos, 'reglas': self.reglas}, fh,
                          ensure_ascii=False, indent=2)
            os.replace(temporal, self.archivo)
        finally:
            if temporal is not None and temporal.exists():
                temporal.unlink()

    def registrar(self, texto):
        clave = normalizar(texto)
        for a in self.atomos:
            if normalizar(a['texto']) == clave:
                return a['id']
        identificador = f'X{len(self.atomos) + 1}'
        self.atomos.append({'id': identificador, 'texto': texto})
        return identificador

    def agregar(self, texto):
        texto = texto.strip()
        if not texto:
            raise ValueError('Escribe una regla.')
        # Requiere "Si ..., entonces ..."; también admite "Si ..., ...".
        partes = re.match(r'^si\s+(.+?)(?:\s*,\s*entonces\s+|\s+entonces\s+|\s*,\s*)(.+?)\s*[.!?]?$',
                           texto, flags=re.I | re.S)
        if not partes:
            raise ValueError('Usa: Si [condición], entonces [resultado].')
        ant, cons = (s.strip(' .,!¡¿?;:') for s in partes.groups())
        izquierda = AnalizadorRecursivo(ant).leer()
        derecha = AnalizadorRecursivo(cons).leer()
        # Cambiar estado solo después de que el análisis completo haya sido válido.
        antes = len(self.atomos)
        expresion = f'{representar(izquierda, self.registrar)} → {representar(derecha, self.registrar)}'
        regla = {'id': f'R{len(self.reglas)+1}', 'texto': texto, 'expresion': expresion}
        self.reglas.append(regla)
        try:
            self.guardar()
        except OSError:
            self.reglas.pop()
            del self.atomos[antes:]
            raise
        return regla

    def borrar_todo(self):
        anteriores = (self.atomos, self.reglas)
        self.atomos, self.reglas = [], []
        try:
            self.guardar()
        except OSError:
            self.atomos, self.reglas = anteriores
            raise


class Aplicacion(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Identificador de reglas lógicas')
        self.geometry('960x640')
        self.minsize(740, 520)
        self.configure(bg='#edf7ee')
        try:
            self.base = BaseConocimiento()
        except ValueError as exc:
            messagebox.showerror('Error al cargar', str(exc) + '\nSe iniciará una sesión vacía.')
            self.base = BaseConocimiento.__new__(BaseConocimiento)
            self.base.archivo = ARCHIVO
            self.base.atomos, self.base.reglas = [], []

        estilo = ttk.Style(self)
        estilo.theme_use('clam')
        estilo.configure('TButton', font=('Segoe UI', 10), padding=9, background='#c7e8ce', foreground='#14452b', bordercolor='#85b994')
        estilo.map('TButton', background=[('active', '#a0d5ad'), ('pressed', '#78bd8b')])
        estilo.configure('TNotebook', background='#edf7ee', borderwidth=0)
        estilo.configure('TNotebook.Tab', background='#c9e6d0', foreground='#14452b', padding=(12, 7))
        estilo.map('TNotebook.Tab', background=[('selected', '#86c99b')])
        estilo.configure('TFrame', background='#edf7ee')
        estilo.configure('Treeview', font=('Segoe UI', 10), rowheight=25, background='#f8fdf9', fieldbackground='#f8fdf9', foreground='#183f29')
        estilo.map('Treeview', background=[('selected', '#78bd8b')], foreground=[('selected', '#123b23')])
        estilo.configure('Treeview.Heading', font=('Segoe UI', 10, 'bold'), background='#b0dbbb', foreground='#17432b')

        tk.Label(self, text='ANALIZADOR DE REGLAS LÓGICAS', bg='#185c37', fg='white',
                 font=('Segoe UI', 22, 'bold'), pady=18).pack(fill='x')
        tk.Label(self, text='Traductor de lenguaje natural a lógica proposicional',
                 bg='#edf7ee', fg='#3b6c4c', font=('Segoe UI', 11)).pack(pady=(12, 4))

        entrada = tk.Frame(self, bg='#edf7ee', padx=20)
        entrada.pack(fill='x', pady=10)
        tk.Label(entrada, text='Escribe una regla:', bg='#edf7ee', font=('Segoe UI', 11, 'bold')).pack(anchor='w')
        self.campo = tk.Text(entrada, height=3, font=('Segoe UI', 11), wrap='word', bd=1, relief='solid', bg='#fbfffb', fg='#17432b', insertbackground='#17432b', highlightbackground='#94caa2')
        self.campo.pack(fill='x', pady=6)
        self.campo.insert('1.0', 'Si Juan estudia y (Juan trabaja o Juan practica), entonces Juan aprueba.')

        botones = tk.Frame(self, bg='#edf7ee', padx=20)
        botones.pack(fill='x', pady=(0, 10))
        for titulo, accion in [('Agregar regla', self.agregar), ('Consultar / actualizar', self.actualizar),
                               ('Ayuda', self.ayuda), ('Borrar datos guardados', self.borrar),
                               ('Salir', self.destroy)]:
            ttk.Button(botones, text=titulo, command=accion).pack(side='left', padx=(0, 8))

        panel = ttk.Notebook(self)
        panel.pack(fill='both', expand=True, padx=20, pady=10)
        hoja_atomos = ttk.Frame(panel)
        hoja_reglas = ttk.Frame(panel)
        panel.add(hoja_atomos, text='Átomos')
        panel.add(hoja_reglas, text='Reglas')
        self.tabla_atomos = self.tabla(hoja_atomos, ('ID', 'Afirmación'), (90, 700))
        self.tabla_reglas = self.tabla(hoja_reglas, ('ID', 'Regla original', 'Expresión lógica'), (70, 450, 420))
        tk.Label(self, text='23310395', anchor='w', bg='#edf7ee', fg='#4c7860', padx=20, font=('Segoe UI', 8)).pack(fill='x', side='bottom', pady=(0, 3))
        self.estado = tk.StringVar()
        tk.Label(self, textvariable=self.estado, anchor='w', bg='#d2ead8',
                 fg='#17432b', padx=20, pady=8, font=('Segoe UI', 9)).pack(fill='x')
        self.actualizar()

    def tabla(self, padre, columnas, anchos):
        marco = ttk.Frame(padre)
        marco.pack(fill='both', expand=True)
        tabla = ttk.Treeview(marco, columns=columnas, show='headings')
        for nombre, ancho in zip(columnas, anchos):
            tabla.heading(nombre, text=nombre)
            tabla.column(nombre, width=ancho, minwidth=60, stretch=True)
        scroll = ttk.Scrollbar(marco, orient='vertical', command=tabla.yview)
        tabla.configure(yscrollcommand=scroll.set)
        tabla.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        return tabla

    def actualizar(self):
        for tabla in (self.tabla_atomos, self.tabla_reglas):
            tabla.delete(*tabla.get_children())
        for a in self.base.atomos:
            self.tabla_atomos.insert('', 'end', values=(a['id'], a['texto']))
        for r in self.base.reglas:
            self.tabla_reglas.insert('', 'end', values=(r['id'], r['texto'], r['expresion']))
        self.estado.set(f"{len(self.base.atomos)} átomos | {len(self.base.reglas)} reglas | Guardado automático en: {self.base.archivo}")

    def agregar(self):
        try:
            r = self.base.agregar(self.campo.get('1.0', 'end').strip())
        except (ValueError, OSError) as exc:
            messagebox.showerror('No se pudo agregar', str(exc))
            return
        self.actualizar()
        messagebox.showinfo('Regla registrada', f"{r['id']} = {r['expresion']}")
        self.campo.delete('1.0', 'end')

    def borrar(self):
        if not messagebox.askyesno('Confirmar borrado',
                                   '¿Eliminar TODOS los átomos y reglas guardados?\nEsta acción no se puede deshacer.'):
            return
        try:
            self.base.borrar_todo()
        except OSError as exc:
            messagebox.showerror('Error al guardar', str(exc))
            return
        self.actualizar()
        messagebox.showinfo('Datos borrados', 'La base de conocimiento está vacía.')

    def ayuda(self):
        messagebox.showinfo('Instrucciones',
            'Escribe reglas de la forma:\n'
            'Si Cuitlahuac estudia y Juan trabaja, entonces Cuitlahuac aprueba.\n\n'
            'Se admiten: y, o, pero, y paréntesis.\n'
            '"y" tiene prioridad sobre "o".\n'
            'Ejemplo: Si (A o B) y C, entonces D.\n\n'
            'Se reutilizan los átomos escritos igual (ignorando mayúsculas y acentos).\n'
            'Los datos se guardan automáticamente después de cada regla.\n'
            'No se incluyen negaciones ni SAT Solver en esta etapa.\n'
            'Usa afirmaciones completas; evita poner "y" u "o" dentro del nombre de un átomo.')


if __name__ == '__main__':
    app = Aplicacion()
    app.mainloop()
