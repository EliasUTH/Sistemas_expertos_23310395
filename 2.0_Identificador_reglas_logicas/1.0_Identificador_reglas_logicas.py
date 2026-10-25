import re
import unicodedata

def normalizar(texto):
    texto = unicodedata.normalize('NFD', texto.casefold())
    texto = ''.join(c for c in texto if unicodedata.category(c) != 'Mn')
    return re.sub(r'\s+', ' ', texto).strip(' .,!¡¿?;:')

def separar_condiciones(texto):
    """Separa 'y', 'o', 'pero' (como y); preserva el conector de cada segmento."""
    piezas = re.split(r'\s+(y|o|pero)\s+', texto, flags=re.IGNORECASE)
    atomos = [piezas[0].strip()]
    operadores = []
    for i in range(1, len(piezas), 2):
        operadores.append('∨' if normalizar(piezas[i]) == 'o' else '∧')
        atomos.append(piezas[i + 1].strip())
    return atomos, operadores


class SistemaReglas:
    def __init__(self):
        self.atomos = {}  # descripción normalizada -> (id, descripción)
        self.reglas = []

    def registrar_atomo(self, descripcion):
        descripcion = descripcion.strip(' .,!¡¿?;:')
        if not descripcion:
            raise ValueError('Se encontró una afirmación vacía.')
        clave = normalizar(descripcion)
        if clave not in self.atomos:
            self.atomos[clave] = (f'X{len(self.atomos) + 1}', descripcion)
        return self.atomos[clave][0]

    def parsear_parte(self, texto):
        segmentos, operadores = separar_condiciones(texto)
        ids = [self.registrar_atomo(s) for s in segmentos]
        expresion = ids[0]
        for operador, id_atomo in zip(operadores, ids[1:]):
            expresion += f' {operador} {id_atomo}'
        return f'({expresion})' if operadores else expresion

    def agregar_regla(self, texto):
        original = texto.strip()
        if not original:
            raise ValueError('La regla está vacía.')
        # Admite 'Si ..., entonces ...' y 'Si ... , ...'
        patron = r'^si\s+(.+?)\s*(?:,\s*entonces\s+|\s+entonces\s+|,\s*)(.+?)\s*[.!?]?\s*$'
        coincidencia = re.match(patron, original, flags=re.IGNORECASE)
        if not coincidencia:
            raise ValueError('Formato inválido. Usa: Si [condiciones], entonces [resultado].')
        antecedente, consecuente = (parte.strip(' .,!¡¿?;:') for parte in coincidencia.groups())
        if not antecedente or not consecuente:
            raise ValueError('La condición y el resultado deben contener afirmaciones.')
        # Validar antes de modificar el catálogo
        for parte in (antecedente, consecuente):
            segmentos, _ = separar_condiciones(parte)
            if any(not s.strip(' .,!¡¿?;:') for s in segmentos):
                raise ValueError('La regla contiene afirmaciones vacías.')
        izquierda = self.parsear_parte(antecedente)
        derecha = self.parsear_parte(consecuente)
        identificador = f'R{len(self.reglas) + 1}'
        expresion = f'{izquierda} → {derecha}'
        self.reglas.append((identificador, original, expresion))
        return identificador, expresion

    def mostrar(self):
        print('\n' + '_' * 55)
        print('ÁTOMOS REGISTRADOS')
        if not self.atomos:
            print('  (ninguno)')
        for ident, descripcion in self.atomos.values():
            print(f'  {ident} = {descripcion}')
        print('\nREGLAS LÓGICAS')
        if not self.reglas:
            print('  (ninguna)')
        for ident, _, expresion in self.reglas:
            print(f'  {ident} = {expresion}')
        print('=' * 55)


def main():
    sistema = SistemaReglas()
    print('_IDENTIFICADOR DE REGLAS LÓGICAS_')
    print('Opciones: mostrar | ayuda | salir')
    while True:
        try:
            entrada = input('\nEscribe una regla o comando: ').strip()
        except (EOFError, KeyboardInterrupt):
            print('\nSaliendo del sistema...')
            break
        comando = normalizar(entrada)
        if comando == 'salir':
            print('Saliendo del sistema...')
            break
        if comando == 'mostrar':
            sistema.mostrar()
        elif comando == 'ayuda':
            print('Formato: Si [afirmación] y/o [afirmación], entonces [afirmación].')
            print('Incluye sujeto explícito en cada afirmación: "Cuitlahuac estudia y Cuitlahuac trabaja".')
            print('No se interpretan negaciones ni expresiones con paréntesis en esta etapa.')
        elif not entrada:
            print('Escribe una regla para continuar.')
        else:
            try:
                ident, expresion = sistema.agregar_regla(entrada)
                print(f'Regla agregada: {ident} = {expresion}')
                sistema.mostrar()
            except ValueError as exc:
                print(f'Error: {exc}')


if __name__ == '__main__':
    main()
