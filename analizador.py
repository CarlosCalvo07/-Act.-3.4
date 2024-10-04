import re
from flask import Flask, render_template, request, redirect, url_for
from difflib import get_close_matches

app = Flask(__name__)

# Definir las expresiones regulares para los diferentes tipos de tokens
token_patterns = {
    'PR': r'\b(programa|int|read|printf|end)\b',  # Palabras reservadas (sin 'suma')
    'ID': r'\b[a-zA-Z_][a-zA-Z0-9_]*\b',              # Identificadores
    'NUM': r'\b\d+\b',                                # Números
    'STRING': r'\"[^\"]*\"',                           # Cadenas de texto
    'SYMBOL': r'[;:,.=(){}+\-*/]'                      # Símbolos, incluye operadores aritméticos
}

# Lista de todas las palabras válidas: palabras reservadas, operadores, símbolos
valid_tokens = ['programa', 'int', 'read', 'printf', 'end', ';', ':', ',', '=', '(', ')', '{', '}', '+', '-', '*', '/']

# Lista de palabras reservadas que necesitan ';' al final
reserved_words_requiring_semicolon = ['read', 'printf', 'end']

# Lista de palabras reservadas (sin 'suma')
reserved_words = ['programa', 'int', 'read', 'printf', 'end']

# Expresión regular para una asignación correcta
assignment_pattern = re.compile(r'^\s*[a-zA-Z_][a-zA-Z0-9_]*\s*=\s*[a-zA-Z0-9_]+(\s*[\+\-\*/]\s*[a-zA-Z0-9_]+)*\s*;\s*$')

# Función para analizar el código y extraer los tokens
def lex_analyze(code):
    tokens = []
    errors = []  # Lista para almacenar errores y sugerencias
    symbols_stack = []  # Pila para verificar el balanceo de paréntesis, llaves, etc.
    
    # Diccionario para contar los diferentes tipos de tokens
    token_count = {
        'Palabra Reservada': 0,
        'Identificador': 0,
        'Variable': 0,
        'Número': 0,
        'Cadena': 0,
        'Símbolo': 0,  # Cambiamos "Symbol" por "Símbolo" aquí también
    }
    
    lines = code.splitlines()
    for line_number, line in enumerate(lines, start=1):
        index = 0
        prev_token_type = None  # Guardamos el tipo del token anterior
        prev_token_value = None  # Guardamos el valor del token anterior

        # Verificación de declaraciones múltiples tipo 'int'
        if re.match(r'\bint\b', line):
            variable_list = line.replace('int', '').strip()
            variables = variable_list.split(',')
            for variable in variables:
                variable = variable.strip()
                if not re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_]*', variable):
                    errors.append(f"Línea {line_number}: Error en la declaración de variable '{variable}'.")
            if not line.strip().endswith(';'):
                errors.append(f"Línea {line_number}: Falta ';' al final de la declaración de variables.")
            if len(variables) > 1 and not all(',' in subline or subline.endswith(';') for subline in line.split(';')[:-1]):
                errors.append(f"Línea {line_number}: Falta una coma en la declaración de variables '{line.strip()}'.")
                
        # Verificar si la línea sigue la estructura de una asignación
        if assignment_pattern.match(line):
            pass
        else:
            if '=' not in line and any(op in line for op in ['+', '-', '*', '/']):
                errors.append(f"Línea {line_number}: Falta un signo de asignación '=' en la instrucción.")
            elif '=' in line:
                expression = line.split('=')[1].strip()
                if not re.search(r'[\+\-\*/]', expression) and len(expression) > 1:
                    errors.append(f"Línea {line_number}: Falta un operador en la expresión '{line.strip()}'.")
        
        while index < len(line):
            if line[index].isspace():
                index += 1
                continue

            match = None
            for token_type, pattern in token_patterns.items():
                regex = re.compile(pattern)
                match = regex.match(line, index)
                if match:
                    token_value = match.group()

                    # Actualizar el contador de tokens según el tipo
                    if token_type == 'PR':
                        token_count['Palabra Reservada'] += 1
                    elif token_type == 'ID':
                        token_count['Identificador'] += 1
                        token_count['Variable'] += 1
                    elif token_type == 'NUM':
                        token_count['Número'] += 1
                    elif token_type == 'STRING':
                        token_count['Cadena'] += 1
                    elif token_type == 'SYMBOL':
                        token_count['Símbolo'] += 1

                    if token_value in ['(', '{']:
                        symbols_stack.append(token_value)
                    elif token_value == ')' and (not symbols_stack or symbols_stack.pop() != '('):
                        errors.append(f"Línea {line_number}: Falta '(' para el símbolo ')'.")
                    elif token_value == '}' and (not symbols_stack or symbols_stack.pop() != '{'):
                        errors.append(f"Línea {line_number}: Falta '{{' para el símbolo '}}'.")

                    if token_type == 'PR' and token_value in reserved_words_requiring_semicolon:
                        if not line.strip().endswith(';'):
                            errors.append(f"Línea {line_number}: Falta ';' después de '{token_value}'.")
                    
                    if token_type in ['ID', 'NUM', 'STRING'] and index == len(line) - 1 and line[-1] != ';':
                        errors.append(f"Línea {line_number}: Falta ';' al final de la instrucción.")

                    # Verificar si "suma" está mal escrito
                    token_category, error_message, suggestion = categorize_token(token_value, token_type)
                    if error_message:
                        errors.append(f"Línea {line_number}: {error_message}")
                        if suggestion:
                            errors.append(f"Sugerencia: {suggestion}")
                    
                    tokens.append({
                        'line': line_number,
                        'token': token_value,
                        'palabra_reservada': 'X' if token_type == 'PR' else '',
                        'identificador': 'X' if token_type == 'ID' else '',
                        'variable': 'X' if token_type == 'ID' else '',
                        'numero': 'X' if token_type == 'NUM' else '',
                        'cadena': 'X' if token_type == 'STRING' else '',
                        'simbolo': 'X' if token_type == 'SYMBOL' else '',
                        'tipo': 'Símbolo' if token_type == 'SYMBOL' else token_category  # Aquí cambiamos "Symbol" por "Símbolo"
                    })

                    prev_token_type = token_type
                    prev_token_value = token_value
                    index = match.end()
                    break
            if not match:
                token_value = line[index]
                closest_match = find_closest_match(token_value)
                error_message = f"Token inválido: '{token_value}'"
                suggestion = f"Sugerencia: ¿Quisiste decir '{closest_match}'?" if closest_match else ''
                errors.append(f"Línea {line_number}: {error_message}")
                if suggestion:
                    errors.append(suggestion)
                tokens.append({
                    'line': line_number,
                    'token': token_value,
                    'palabra_reservada': '',
                    'identificador': '',
                    'variable': '',
                    'numero': '',
                    'cadena': '',
                    'simbolo': '',
                    'tipo': 'Desconocido'
                })
                index += 1

    for symbol in symbols_stack:
        if symbol == '(':
            errors.append(f"Error: Falta ')' para el símbolo '('.")
        elif symbol == '{':
            errors.append(f"Error: Falta '}}' para el símbolo '{{'.")

    return tokens, errors, token_count

# Categorizar el token y verificar si es un identificador mal escrito
def categorize_token(token, token_type):
    error_message = ''
    suggestion = ''
    if token_type == 'PR' or token_type == 'SYMBOL':
        if token not in valid_tokens:
            closest_match = find_closest_match(token)
            error_message = f"Error: '{token}' parece estar mal escrito."
            suggestion = f"Sugerencia: ¿Quisiste decir '{closest_match}'?" if closest_match else ''
        return token_type.capitalize(), error_message, suggestion

    elif token_type == 'ID':
        if token in reserved_words:
            error_message = f"Error: '{token}' es una palabra reservada, no un identificador."
            return 'Identificador', error_message, ''
        
        # Aquí se verifica si es un identificador mal escrito, incluyendo 'suma'
        if token != "suma" and find_closest_match(token) == "suma":
            error_message = f"Error: '{token}' parece estar mal escrito como identificador."
            suggestion = f"Sugerencia: ¿Quisiste decir 'suma'?"
        return 'Identificador', error_message, suggestion

    elif token_type == 'NUM':
        return token_type.capitalize(), error_message, suggestion

    elif token_type == 'STRING':
        return 'Cadena', error_message, suggestion

    return 'Desconocido', error_message, suggestion

# Buscar la coincidencia más cercana
def find_closest_match(token):
    closest_matches = get_close_matches(token, reserved_words + valid_tokens + ["suma"], n=1, cutoff=0.8)
    return closest_matches[0] if closest_matches else None

@app.route('/')
def index():
    return render_template('vista.html', code='', tokens=[], errors=[], token_count={})

@app.route('/analyze', methods=['POST'])
def analyze():
    code = request.form['code']
    tokens, errors, token_count = lex_analyze(code)
    return render_template('vista.html', tokens=tokens, code=code, errors=errors, token_count=token_count)

@app.route('/reset', methods=['POST'])
def reset():
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)