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
    """Analizador por descenso recursivo adaptado para soportar negación y equivalencia.
    Precedencia: NO > Y > O > SII.
    """
    def __init__(self, texto):
        texto = re.sub(r'\bsi\s+y\s+solo\s+si\b', '↔', texto, flags=re.I)
        self.tokens = re.findall(r'\(|\)|\b(?:y|o|pero|no)\b|↔|[^()\s]+', texto, flags=re.I)
        self.pos = 0

    def actual(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def operador(self):
        t = self.actual()
        if not t: return None
        if t == '↔': return '↔'
        n = normalizar(t)
        return n if n in ('y', 'o', 'pero', 'no') else None

    def leer(self):
        if not self.tokens:
            raise ValueError('No hay afirmaciones para analizar.')
        nodo = self.equivalencia()
        if self.actual() is not None:
            raise ValueError(f'Elemento inesperado: {self.actual()}')
        return nodo

    def equivalencia(self):
        nodo = self.disyuncion()
        while self.operador() == '↔':
            self.pos += 1
            nodo = ('↔', nodo, self.disyuncion())
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
        op = self.operador()
        if op == 'no':
            self.pos += 1
            return ('¬', self.termino())
        
        if self.actual() == '(':
            self.pos += 1
            nodo = self.equivalencia()
            if self.actual() != ')':
                raise ValueError('Falta cerrar un paréntesis.')
            self.pos += 1
            return nodo
        
        palabras = []
        while self.actual() is not None and self.actual() not in ('(', ')') and not self.operador():
            palabras.append(self.actual())
            self.pos += 1
            
        afirmacion = ' '.join(palabras).strip(' .,!¡¿?;:')
        
        if normalizar(afirmacion).startswith('no '):
            afirmacion_limpia = afirmacion[3:].strip()
            return ('¬', ('atomo', afirmacion_limpia))
            
        if not afirmacion:
            raise ValueError('Hay una afirmación incompleta junto a un conector.')
        if self.actual() == '(':
            raise ValueError('Falta un conector antes del paréntesis.')
            
        return ('atomo', afirmacion)

def representar(nodo, registrar):
    if nodo[0] == 'atomo':
        return registrar(nodo[1])
    if nodo[0] == '¬':
        return f'¬{representar(nodo[1], registrar)}'
    _, izq, der = nodo
    return f'({representar(izq, registrar)} {nodo[0]} {representar(der, registrar)})'

# --- Motor de Tableaux Semántico ---
def neg(f):
    if f[0] == '¬': return f[1]
    return ('¬', f)

def evaluar_tableaux(formulas):
    ramas = [[(f, False) for f in formulas]]
    ramas_finalizadas = []

    while ramas:
        rama = ramas.pop(0)
        literales = [f for f, _ in rama if f[0] == 'atomo' or (f[0] == '¬' and f[1][0] == 'atomo')]
        cerrada = False
        for lit in literales:
            if neg(lit) in literales:
                cerrada = True
                break
                
        if cerrada:
            ramas_finalizadas.append({'cerrada': True, 'literales': literales})
            continue

        idx_aplicar = -1
        for i, (f, aplicada) in enumerate(rama):
            if not aplicada and not (f[0] == 'atomo' or (f[0] == '¬' and f[1][0] == 'atomo')):
                idx_aplicar = i
                break
                
        if idx_aplicar == -1:
            ramas_finalizadas.append({'cerrada': False, 'literales': literales})
            continue

        f, _ = rama[idx_aplicar]
        rama[idx_aplicar] = (f, True)
        
        nueva_rama1 = list(rama)
        nueva_rama2 = None
        
        if f[0] == '¬' and f[1][0] == '¬':
            nueva_rama1.append((f[1][1], False))
        elif f[0] == '∧':
            nueva_rama1.append((f[1], False))
            nueva_rama1.append((f[2], False))
        elif f[0] == '¬' and f[1][0] == '∨':
            nueva_rama1.append((neg(f[1][1]), False))
            nueva_rama1.append((neg(f[1][2]), False))
        elif f[0] == '¬' and f[1][0] == '→':
            nueva_rama1.append((f[1][1], False))
            nueva_rama1.append((neg(f[1][2]), False))
        elif f[0] == '∨':
            nueva_rama2 = list(rama)
            nueva_rama1.append((f[1], False))
            nueva_rama2.append((f[2], False))
        elif f[0] == '→':
            nueva_rama2 = list(rama)
            nueva_rama1.append((neg(f[1]), False))
            nueva_rama2.append((f[2], False))
        elif f[0] == '↔':
            nueva_rama2 = list(rama)
            nueva_rama1.append((f[1], False))
            nueva_rama1.append((f[2], False))
            nueva_rama2.append((neg(f[1]), False))
            nueva_rama2.append((neg(f[2]), False))
        elif f[0] == '¬' and f[1][0] == '∧':
            nueva_rama2 = list(rama)
            nueva_rama1.append((neg(f[1][1]), False))
            nueva_rama2.append((neg(f[1][2]), False))
        elif f[0] == '¬' and f[1][0] == '↔':
            nueva_rama2 = list(rama)
            nueva_rama1.append((f[1][1], False))
            nueva_rama1.append((neg(f[1][2]), False))
            nueva_rama2.append((neg(f[1][1]), False))
            nueva_rama2.append((f[1][2], False))

        ramas.append(nueva_rama1)
        if nueva_rama2:
            ramas.append(nueva_rama2)

    return ramas_finalizadas

class BaseConocimiento:
    def __init__(self, archivo=ARCHIVO):
        self.archivo = Path(archivo)
        self.atomos = []
        self.reglas = []
        self.cargar()

    def cargar(self):
        if not self.archivo.exists(): return
        try:
            datos = json.loads(self.archivo.read_text(encoding='utf-8'))
            self.atomos = datos.get('atomos', [])
            self.reglas = datos.get('reglas', [])
        except (OSError, ValueError, KeyError, TypeError):
            self.atomos, self.reglas = [], []

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
        letras = "pqrstuvwxyzabcdefghijklmno"
        identificador = letras[len(self.atomos) % 26]
        self.atomos.append({'id': identificador, 'texto': texto})
        return identificador

    def agregar(self, texto):
        texto = texto.strip()
        if not texto: raise ValueError('Escribe una regla o un hecho.')
        
        partes = re.match(r'^si\s+(.+?)(?:\s*,\s*entonces\s+|\s+entonces\s+|\s*,\s*)(.+?)\s*[.!?]?$', texto, flags=re.I | re.S)
        
        if partes:
            ant, cons = (s.strip(' .,!¡¿?;:') for s in partes.groups())
            izquierda = AnalizadorRecursivo(ant).leer()
            derecha = AnalizadorRecursivo(cons).leer()
            ast = ('→', izquierda, derecha)
        else:
            texto_limpio = texto.strip(' .,!¡¿?;:')
            ast = AnalizadorRecursivo(texto_limpio).leer()
            
        antes = len(self.atomos)
        expresion = representar(ast, self.registrar)
        regla = {'id': f'R{len(self.reglas)+1}', 'texto': texto, 'expresion': expresion, 'ast': ast}
        self.reglas.append(regla)
        
        try:
            self.guardar()
        except OSError:
            self.reglas.pop()
            del self.atomos[antes:]
            raise
        return regla

    def borrar_todo(self):
        self.atomos, self.reglas = [], []
        self.guardar()

class Aplicacion(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Identificador de reglas lógicas y SAT Solver')
        self.geometry('1024x720')
        self.minsize(800, 600)
        self.configure(bg='#edf7ee')
        self.base = BaseConocimiento()

        estilo = ttk.Style(self)
        estilo.theme_use('clam')
        estilo.configure('TButton', font=('Segoe UI', 10), padding=9, background='#c7e8ce', foreground='#14452b')
        estilo.configure('Treeview', font=('Segoe UI', 10), rowheight=25)
        estilo.configure('Treeview.Heading', font=('Segoe UI', 10, 'bold'), background='#b0dbbb')

        tk.Label(self, text='ANALIZADOR LÓGICO Y TABLEAUX', bg='#185c37', fg='white',
                 font=('Segoe UI', 18, 'bold'), pady=15).pack(fill='x')

        entrada = tk.Frame(self, bg='#edf7ee', padx=20)
        entrada.pack(fill='x', pady=10)
        tk.Label(entrada, text='Escribe una regla o hecho:', bg='#edf7ee', font=('Segoe UI', 11, 'bold')).pack(anchor='w')
        self.campo = tk.Text(entrada, height=3, font=('Segoe UI', 11), wrap='word', bd=1, relief='solid')
        self.campo.pack(fill='x', pady=6)
        self.campo.insert('1.0', 'Si es de día, entonces voy a trabajar.')

        botones = tk.Frame(self, bg='#edf7ee', padx=20)
        botones.pack(fill='x', pady=(0, 10))
        
        # --- SE AÑADIÓ EL BOTÓN "VER ÁRBOL (REGLA)" ---
        for titulo, accion in [('Agregar a Base', self.agregar), 
                               ('Evaluar Tableaux', self.evaluar_tableaux),
                               ('Ver Árbol (Regla)', self.ver_arbol_regla),
                               ('Ayuda', self.ayuda), 
                               ('Borrar todo', self.borrar)]:
            ttk.Button(botones, text=titulo, command=accion).pack(side='left', padx=(0, 8))

        panel = ttk.Notebook(self)
        panel.pack(fill='both', expand=True, padx=20, pady=10)
        hoja_atomos = ttk.Frame(panel)
        hoja_reglas = ttk.Frame(panel)
        panel.add(hoja_atomos, text='Átomos (Diccionario)')
        panel.add(hoja_reglas, text='Base de Conocimiento')
        self.tabla_atomos = self.tabla(hoja_atomos, ('Letra', 'Proposición Simple'), (80, 700))
        self.tabla_reglas = self.tabla(hoja_reglas, ('ID', 'Original', 'Fórmula Lógica'), (60, 450, 400))
        self.actualizar()

    def tabla(self, padre, columnas, anchos):
        marco = ttk.Frame(padre)
        marco.pack(fill='both', expand=True)
        tabla = ttk.Treeview(marco, columns=columnas, show='headings')
        for nombre, ancho in zip(columnas, anchos):
            tabla.heading(nombre, text=nombre)
            tabla.column(nombre, width=ancho, stretch=True)
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

    def agregar(self):
        try:
            self.base.agregar(self.campo.get('1.0', 'end').strip())
        except (ValueError, OSError) as exc:
            messagebox.showerror('Error', str(exc))
            return
        self.actualizar()
        self.campo.delete('1.0', 'end')
        
    def evaluar_tableaux(self):
        if not self.base.reglas:
            messagebox.showinfo('Aviso', 'La base de conocimiento está vacía.')
            return
            
        formulas_ast = [r['ast'] for r in self.base.reglas]
        ramas = evaluar_tableaux(formulas_ast)
        
        texto_resultado = "RESULTADOS DEL ÁRBOL DE VERDAD (TABLEAUX)\n"
        texto_resultado += "="*50 + "\n\n"
        
        abiertas = 0
        cerradas = 0
        
        for i, rama in enumerate(ramas, 1):
            estado = "✕ CERRADA" if rama['cerrada'] else "◯ ABIERTA"
            texto_resultado += f"Rama {i}: {estado}\n"
            
            if rama['cerrada']:
                cerradas += 1
            else:
                abiertas += 1
                asignaciones = []
                for lit in set(rama['literales']):
                    if lit[0] == 'atomo':
                        asignaciones.append(f"{self.base.registrar(lit[1])} = V")
                    elif lit[0] == '¬':
                        asignaciones.append(f"{self.base.registrar(lit[1][1])} = F")
                
                letras_rama = [a.split(' =')[0] for a in asignaciones]
                for a in self.base.atomos:
                    if a['id'] not in letras_rama:
                        asignaciones.append(f"{a['id']} = V/F (Libre)")
                        
                texto_resultado += f"Modelo (Asignaciones): {', '.join(asignaciones)}\n"
            texto_resultado += "-"*50 + "\n"
            
        if abiertas == 0:
            texto_resultado += "\nCONCLUSIÓN: La base de conocimiento es INSATISFACTIBLE (Todas las ramas cerraron)."
        else:
            texto_resultado += f"\nCONCLUSIÓN: La base es SATISFACTIBLE bajo {abiertas} escenario(s) posibles."
            
        vent = tk.Toplevel(self)
        vent.title('Resultados Tableaux')
        vent.geometry('600x500')
        txt = tk.Text(vent, font=('Consolas', 11), padx=10, pady=10)
        txt.pack(fill='both', expand=True)
        txt.insert('1.0', texto_resultado)
        txt.config(state='disabled')

    # --- NUEVA FUNCIÓN PARA DIBUJAR EL ÁRBOL SEMÁNTICO DE UNA REGLA ---
    def ver_arbol_regla(self):
        seleccion = self.tabla_reglas.selection()
        if not seleccion:
            messagebox.showwarning('Aviso', 'Selecciona una regla de la Base de Conocimiento primero.')
            return
            
        item = self.tabla_reglas.item(seleccion[0])
        id_regla = item['values'][0]
        
        ast_objetivo = None
        for r in self.base.reglas:
            if r['id'] == id_regla:
                ast_objetivo = r['ast']
                break
                
        if not ast_objetivo: return

        vent = tk.Toplevel(self)
        vent.title(f'Árbol Semántico - Regla {id_regla}')
        vent.geometry('800x600')
        vent.configure(bg='white')
        
        canvas = tk.Canvas(vent, bg='white', highlightthickness=0)
        canvas.pack(fill='both', expand=True)

        def dibujar_nodo(nodo, x, y, dx):
            if nodo[0] == 'atomo':
                canvas.create_oval(x-20, y-15, x+20, y+15, fill="#d4edda", outline="#28a745")
                canvas.create_text(x, y, text=self.base.registrar(nodo[1]), font=("Segoe UI", 12, "bold"))
                return
            if nodo[0] == '¬':
                canvas.create_oval(x-15, y-15, x+15, y+15, fill="#f8d7da", outline="#dc3545")
                canvas.create_text(x, y, text='¬', font=("Segoe UI", 12, "bold"))
                canvas.create_line(x, y+15, x, y+50, fill="#6c757d", width=2)
                dibujar_nodo(nodo[1], x, y+65, dx)
                return
            
            # Conectivos binarios (Y, O, Entonces, SSS)
            canvas.create_oval(x-20, y-15, x+20, y+15, fill="#cce5ff", outline="#007bff")
            canvas.create_text(x, y, text=nodo[0], font=("Segoe UI", 12, "bold"))
            
            # Ramificaciones (Izquierda y Derecha)
            canvas.create_line(x-10, y+10, x-dx, y+50, fill="#6c757d", width=2)
            canvas.create_line(x+10, y+10, x+dx, y+50, fill="#6c757d", width=2)
            
            dibujar_nodo(nodo[1], x-dx, y+65, max(40, dx/1.8))
            dibujar_nodo(nodo[2], x+dx, y+65, max(40, dx/1.8))

        canvas.update()
        ancho_canvas = 800
        dibujar_nodo(ast_objetivo, ancho_canvas // 2, 40, ancho_canvas // 4)

    def borrar(self):
        if messagebox.askyesno('Borrar', '¿Eliminar todos los datos?'):
            self.base.borrar_todo()
            self.actualizar()

    def ayuda(self):
        messagebox.showinfo('Ayuda', 
            'Conectivos soportados: "y", "o", "no", "si ... entonces", "si y solo si".\n'
            'Puedes ingresar reglas enteras o hechos simples (ej. "Es de día").\n'
            'Selecciona una regla en la tabla y pulsa "Ver Árbol (Regla)" para visualizar su estructura.\n'
            'Utiliza "Evaluar Tableaux" para ver la expansión lógica de toda la base.')

if __name__ == '__main__':
    app = Aplicacion()
    app.mainloop()