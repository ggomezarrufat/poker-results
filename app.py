from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import pandas as pd
import os
from datetime import datetime, date
import hashlib

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tu_clave_secreta_aqui'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///poker_results.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Crear directorio de uploads si no existe
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

# Modelo de base de datos para los resultados de poker
class PokerResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, nullable=False)
    hora = db.Column(db.Time, nullable=True)  # Nueva columna para la hora
    tipo_movimiento = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.String(500), nullable=False)
    importe = db.Column(db.Float, nullable=False)
    categoria = db.Column(db.String(100), nullable=False)
    tipo_juego = db.Column(db.String(100), nullable=False)
    nivel_buyin = db.Column(db.String(20), nullable=True)  # Micro, Bajo, Medio, Alto
    sala = db.Column(db.String(50), nullable=False)  # WPN, Pokerstars, etc.
    hash_duplicado = db.Column(db.String(64), unique=True, nullable=False)  # Para detectar duplicados
    fecha_importacion = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<PokerResult {self.fecha} - {self.descripcion} - {self.importe}>'

# Función para generar hash único para detectar duplicados
def generar_hash_duplicado(fecha, hora, payment_method, descripcion, money_in, money_out, sala):
    cadena = f"{fecha}_{hora}_{payment_method}_{descripcion}_{money_in}_{money_out}_{sala}"
    return hashlib.sha256(cadena.encode()).hexdigest()

# Función para categorizar movimientos automáticamente
def categorizar_movimiento(payment_category, payment_method, description):
    """Categoriza automáticamente los movimientos basándose en los datos de WPN"""
    
    # Mapeo de categorías de WPN a nuestras categorías
    categoria_map = {
        'OnDemand Tournament': 'Torneo',
        'Scheduled Tournament': 'Torneo',
        'Bonuses': 'Bonus',
        'Deposit': 'Depósito',
        'Comp Points': 'Puntos',
        'P2P': 'Transferencia'
    }
    
    # Mapeo de métodos de pago a tipos de movimiento
    tipo_movimiento_map = {
        'Winnings': 'Ganancia',
        'Buy In': 'Buy-in',
        'Reentry Buy In': 'Reentry Buy In',
        'Unregister Buy In': 'Unregister Buy In',
        'Fee': 'Fee',
        'Reentry Fee': 'Reentry Fee',
        'Unregister Fee': 'Unregister Fee',
        'Bounty': 'Bounty',
        'Sit & Crush Jackpot': 'Sit & Crush Jackpot',
        'Deposit': 'Depósito',
        'Withdrawal': 'Retiro',
        'Achievements': 'Bonus',
        'Points Exchange': 'Puntos',
        'Player2Player': 'Transferencia',
        'Money Added': 'Money Added',
        'Money Out': 'Money Out',
        'Money In': 'Money In',
        'Payout': 'Payout'
    }
    
    categoria = categoria_map.get(payment_category, 'Otro')
    tipo_movimiento = tipo_movimiento_map.get(payment_method, 'Otro')
    
    # Determinar tipo de juego basándose en la descripción
    desc_lower = description.lower()
    
    # CORRECCIÓN: Si el tipo de movimiento es Money Added, Money Out o Money In, 
    # la categoría debe ser Cash
    if tipo_movimiento in ['Money Added', 'Money Out', 'Money In']:
        categoria = 'Cash'
    
    # CORRECCIÓN: Si el tipo de movimiento es Payout, la categoría debe ser Retiro
    if tipo_movimiento == 'Payout':
        categoria = 'Retiro'
    
    # CORRECCIÓN: Si el tipo de movimiento es de torneo y la descripción contiene indicadores de torneo,
    # la categoría debe ser Torneo
    tipos_movimiento_torneo = ['Buy-in', 'Ganancia', 'Bounty', 'Fee', 'Reentry Fee', 'Reentry Buy In', 'Unregister Buy In', 'Unregister Fee', 'Sit & Crush Jackpot']
    if tipo_movimiento in tipos_movimiento_torneo and any(indicator in desc_lower for indicator in ['$', 'gtd', 'turbo', 'on demand', 'sit & go', 'sit&go', 'sitngo']):
        categoria = 'Torneo'
    if 'stud hi/lo' in desc_lower or 'stud hi lo' in desc_lower:
        tipo_juego = 'Stud Hi/Lo'
    elif 'nlo8' in desc_lower or 'nl omaha 8' in desc_lower:
        tipo_juego = 'NLO8'
    elif 'plo hi/lo' in desc_lower or 'plo hi lo' in desc_lower:
        tipo_juego = 'PLO Hi/Lo'
    elif '5c plo8' in desc_lower or '5c plo 8' in desc_lower:
        tipo_juego = '5C PLO8'
    elif 'plo8' in desc_lower or 'plo 8' in desc_lower:
        tipo_juego = 'PLO8'
    elif 'plo' in desc_lower:
        tipo_juego = 'PLO'
    elif 'sit' in desc_lower and 'go' in desc_lower:
        tipo_juego = 'Sit & Go'
    elif 'nlh' in desc_lower or 'holdem' in desc_lower:
        tipo_juego = 'NLH'
    elif 'tournament' in desc_lower or 'torneo' in desc_lower:
        tipo_juego = 'Torneo'
    else:
        tipo_juego = 'Cash'
    
    return categoria, tipo_movimiento, tipo_juego

def clasificar_nivel_buyin(importe):
    """Clasifica el nivel de buy-in de un torneo"""
    if importe < 0:
        importe = abs(importe)  # Convertir a positivo
    
    if importe < 5:
        return 'Micro'
    elif importe < 25:
        return 'Bajo'
    elif importe < 100:
        return 'Medio'
    else:
        return 'Alto'

def reclasificar_niveles_buyin_automatica():
    """Reclasifica automáticamente los niveles de buy-in para registros de torneos (Bounty, Winnings, Sit & Crush Jackpot, Fee, Reentry Fee, Reentry Buy In)"""
    try:
        # Obtener todos los registros de torneos con Buy In que ya tienen nivel_buyin
        buyins_clasificados = PokerResult.query.filter(
            PokerResult.categoria == 'Torneo',
            PokerResult.tipo_movimiento == 'Buy In',
            PokerResult.nivel_buyin.isnot(None)
        ).all()
        
        if not buyins_clasificados:
            return 0
        
        # Obtener registros de torneos sin clasificar (todos los tipos de movimiento de torneos)
        registros_sin_clasificar = PokerResult.query.filter(
            PokerResult.categoria == 'Torneo',
            PokerResult.tipo_movimiento.in_(['Bounty', 'Winnings', 'Sit & Crush Jackpot', 'Fee', 'Reentry Fee', 'Reentry Buy In', 'Unregister Buy In', 'Unregister Fee', 'Tournament Rebuy']),
            PokerResult.nivel_buyin.is_(None)
        ).all()
        
        if not registros_sin_clasificar:
            return 0
        
        # Crear un diccionario de descripción -> nivel_buyin para búsqueda rápida
        descripcion_nivel = {}
        for buyin in buyins_clasificados:
            descripcion_nivel[buyin.descripcion] = buyin.nivel_buyin
        
        # Reclasificar registros de torneos
        reclasificados = 0
        
        for registro in registros_sin_clasificar:
            try:
                nivel_buyin = None
                
                # Método 1: Búsqueda exacta por descripción
                if registro.descripcion in descripcion_nivel:
                    nivel_buyin = descripcion_nivel[registro.descripcion]
                else:
                    # Método 2: Búsqueda por ID del torneo (primeros números)
                    partes = registro.descripcion.split(' ', 1)
                    if len(partes) > 1:
                        torneo_id = partes[0]
                        
                        # Buscar Buy In que comience con el mismo ID
                        for buyin_desc, nivel in descripcion_nivel.items():
                            if buyin_desc.startswith(torneo_id + ' '):
                                nivel_buyin = nivel
                                break
                
                # Método 3: Si no se encuentra por descripción o ID, clasificar por importe
                if not nivel_buyin:
                    nivel_buyin = clasificar_nivel_buyin(registro.importe)
                
                if nivel_buyin:
                    registro.nivel_buyin = nivel_buyin
                    reclasificados += 1
                    
            except Exception as e:
                print(f"Error reclasificando registro {registro.id}: {e}")
                continue
        
        # Guardar cambios
        if reclasificados > 0:
            db.session.commit()
        
        return reclasificados
        
    except Exception as e:
        print(f"Error en reclasificación automática: {e}")
        return 0

def reclasificar_tipos_juego_automatica():
    """Reclasifica automáticamente los tipos de juego para registros relacionados (Reentry Buy In, Winnings, Bounty, etc.)"""
    try:
        # Obtener todos los registros Buy In con tipo de juego específico
        buyins_clasificados = PokerResult.query.filter(
            PokerResult.categoria == 'Torneo',
            PokerResult.tipo_movimiento == 'Buy In',
            PokerResult.tipo_juego != 'Torneo'  # Solo los que tienen tipo específico
        ).all()
        
        if not buyins_clasificados:
            return 0
        
        # Crear diccionario de descripción -> tipo_juego para búsqueda rápida
        descripcion_tipo_juego = {}
        for buyin in buyins_clasificados:
            descripcion_tipo_juego[buyin.descripcion] = buyin.tipo_juego
        
        # Obtener registros que necesitan reclasificación (solo los que tienen tipo genérico)
        registros_sin_clasificar = PokerResult.query.filter(
            PokerResult.categoria == 'Torneo',
            PokerResult.tipo_movimiento.in_(['Reentry Buy In', 'Winnings', 'Bounty', 'Fee', 'Reentry Fee', 'Unregister Buy In', 'Unregister Fee', 'Sit & Crush Jackpot', 'Tournament Rebuy']),
            PokerResult.tipo_juego == 'Torneo'  # Solo los que tienen tipo genérico
        ).all()
        
        if not registros_sin_clasificar:
            return 0
        
        reclasificados = 0
        for registro in registros_sin_clasificar:
            try:
                tipo_juego = None
                
                # Método 1: Búsqueda exacta por descripción
                if registro.descripcion in descripcion_tipo_juego:
                    tipo_juego = descripcion_tipo_juego[registro.descripcion]
                else:
                    # Método 2: Búsqueda por ID del torneo (primeros números)
                    partes = registro.descripcion.split(' ', 1)
                    if len(partes) > 1:
                        torneo_id = partes[0]
                        
                        # Buscar Buy In que comience con el mismo ID
                        for buyin_desc, tipo in descripcion_tipo_juego.items():
                            if buyin_desc.startswith(torneo_id + ' '):
                                tipo_juego = tipo
                                break
                
                if tipo_juego:
                    registro.tipo_juego = tipo_juego
                    reclasificados += 1
                    print(f"✅ Reclasificado: {registro.tipo_movimiento} -> {tipo_juego}")
                    
            except Exception as e:
                print(f"Error reclasificando tipo de juego para registro {registro.id}: {e}")
                continue
        
        if reclasificados > 0:
            db.session.commit()
        
        return reclasificados
        
    except Exception as e:
        print(f"Error en reclasificación de tipos de juego: {e}")
        return 0

# Función para procesar archivos de WPN
def procesar_archivo_wpn(filepath):
    """Procesa archivos Excel de WPN y los importa a la base de datos"""
    try:
        # Leer el archivo Excel
        df = pd.read_excel(filepath)
        print(f"Total registros en archivo: {len(df)}")
        
        # Limpiar y procesar los datos
        df_original = len(df)
        df = df.dropna(subset=['Date'])  # Eliminar filas sin fecha
        df_sin_fecha = df_original - len(df)
        print(f"Registros eliminados por falta de fecha: {df_sin_fecha}")
        
        resultados_importados = 0
        duplicados_encontrados = 0
        errores_procesamiento = 0
        duplicados_detalle = []  # Lista para almacenar detalles de duplicados
        
        for index, row in df.iterrows():
            try:
                # Procesar fecha y hora - WPN usa formato "HH:MM:SS YYYY-MM-DD"
                fecha_str = str(row['Date'])
                # Convertir formato "01:06:07 2025-09-24" a datetime
                fecha_hora = pd.to_datetime(fecha_str, format='%H:%M:%S %Y-%m-%d')
                fecha = fecha_hora.date()
                hora = fecha_hora.time()
                
                # Obtener valores originales para el hash
                money_in = float(row['Money In'])
                money_out = float(row['Money Out'])
                payment_method = str(row['Payment Method'])
                descripcion = str(row['Description'])
                
                # Determinar importe (Money In - Money Out)
                importe = money_in - money_out
                
                # Categorizar automáticamente
                categoria, _, tipo_juego = categorizar_movimiento(
                    row['Payment Category'], 
                    payment_method, 
                    descripcion
                )
                
                # El tipo de movimiento se extrae directamente de Payment Method
                tipo_movimiento = payment_method
                
                # Generar hash para detectar duplicados usando campos específicos
                hash_duplicado = generar_hash_duplicado(
                    fecha, 
                    hora,
                    payment_method,
                    descripcion,
                    money_in,
                    money_out,
                    'WPN'
                )
                
                # Verificar si ya existe
                if PokerResult.query.filter_by(hash_duplicado=hash_duplicado).first():
                    duplicados_encontrados += 1
                    # Agregar detalle del duplicado
                    duplicados_detalle.append({
                        'fecha': fecha.isoformat(),
                        'hora': hora.isoformat(),
                        'tipo_movimiento': tipo_movimiento,
                        'descripcion': descripcion,
                        'importe': importe,
                        'categoria': categoria,
                        'tipo_juego': tipo_juego
                    })
                    continue
                
                # Calcular nivel de buy-in SOLO para registros Buy In
                nivel_buyin = None
                if categoria == 'Torneo' and tipo_movimiento == 'Buy In':
                    nivel_buyin = clasificar_nivel_buyin(importe)
                
                # Crear nuevo registro
                nuevo_resultado = PokerResult(
                    fecha=fecha,
                    hora=hora,
                    tipo_movimiento=tipo_movimiento,
                    descripcion=descripcion,
                    importe=importe,
                    categoria=categoria,
                    tipo_juego=tipo_juego,
                    nivel_buyin=nivel_buyin,
                    sala='WPN',
                    hash_duplicado=hash_duplicado
                )
                
                db.session.add(nuevo_resultado)
                resultados_importados += 1
                
            except Exception as e:
                errores_procesamiento += 1
                print(f"Error procesando fila {index}: {e}")
                print(f"Datos de la fila: {row.to_dict()}")
                continue
        
        # Guardar en la base de datos
        db.session.commit()
        
        print(f"Resumen del procesamiento:")
        print(f"- Registros en archivo: {df_original}")
        print(f"- Eliminados por falta de fecha: {df_sin_fecha}")
        print(f"- Errores de procesamiento: {errores_procesamiento}")
        print(f"- Duplicados omitidos: {duplicados_encontrados}")
        print(f"- Registros importados: {resultados_importados}")
        
        # Ejecutar reclasificación automática de niveles de buy-in
        print(f"\n=== RECLASIFICACIÓN AUTOMÁTICA DE NIVELES DE BUY-IN ===")
        try:
            reclasificados = reclasificar_niveles_buyin_automatica()
            print(f"Registros reclasificados automáticamente: {reclasificados}")
        except Exception as e:
            print(f"Error en reclasificación automática: {e}")
        
        # Ejecutar reclasificación automática de tipos de juego
        print(f"\n=== RECLASIFICACIÓN AUTOMÁTICA DE TIPOS DE JUEGO ===")
        try:
            tipos_reclasificados = reclasificar_tipos_juego_automatica()
            print(f"Tipos de juego reclasificados automáticamente: {tipos_reclasificados}")
        except Exception as e:
            print(f"Error en reclasificación de tipos de juego: {e}")
        
        return resultados_importados, duplicados_encontrados, duplicados_detalle
        
    except Exception as e:
        db.session.rollback()
        raise Exception(f"Error procesando archivo WPN: {str(e)}")

# Función para procesar archivos de Pokerstars (placeholder)
def procesar_archivo_pokerstars(filepath):
    """Procesa archivos HTML de Pokerstars y los importa a la base de datos"""
    try:
        from bs4 import BeautifulSoup
        import pandas as pd
        
        # Leer y parsear HTML
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        soup = BeautifulSoup(content, 'html.parser')
        table = soup.find('table')
        
        if not table:
            raise Exception("No se encontró tabla en el archivo")
        
        # Obtener filas
        rows = table.find_all('tr')
        if len(rows) < 3:
            raise Exception("Archivo no tiene suficientes filas")
        
        # Headers (segunda fila)
        subheaders = [td.get_text().strip() for td in rows[1].find_all(['td', 'th'])]
        
        # Filas de datos (desde la fila 2)
        data_rows = rows[2:]
        
        # Crear DataFrame
        data = []
        for row in data_rows:
            cells = [td.get_text().strip() for td in row.find_all(['td', 'th'])]
            if len(cells) >= len(subheaders):
                data.append(cells[:len(subheaders)])
            else:
                while len(cells) < len(subheaders):
                    cells.append('')
                data.append(cells)
        
        if not data:
            raise Exception("No se encontraron datos en el archivo")
        
        df = pd.DataFrame(data, columns=subheaders)
        
        # Procesar cada registro
        resultados_importados = 0
        duplicados_encontrados = 0
        duplicados_detalle = []
        
        for index, row in df.iterrows():
            try:
                # Extraer datos básicos
                fecha_str = row.get('Date/Time', '')
                action = row.get('Action', '')
                game = row.get('Game', '')
                amount_str = row.get('Amount', '')
                tournament_id = row.get('Table Name / Player / Tournament #', '')
                
                if not fecha_str or not action:
                    continue
                
                # Parsear fecha y hora
                try:
                    fecha_dt = pd.to_datetime(fecha_str, format='%Y/%m/%d %I:%M %p')
                    fecha = fecha_dt.date()
                    hora = fecha_dt.time()
                except:
                    continue
                
                # Parsear importe
                try:
                    amount_clean = amount_str.replace('(', '-').replace(')', '').replace(',', '')
                    importe = float(amount_clean)
                except:
                    continue
                
                # Categorizar movimiento
                categoria, tipo_movimiento, tipo_juego = categorizar_movimiento_pokerstars(action, game, tournament_id)
                
                # Crear descripción
                descripcion = f"{tournament_id} {game}".strip()
                if not descripcion or descripcion == tournament_id:
                    descripcion = f"{tournament_id} {action}"
                
                # Generar hash para duplicados
                hash_duplicado = generar_hash_duplicado(fecha, hora, action, descripcion, importe, 0, 'Pokerstars')
                
                # Verificar duplicados
                if PokerResult.query.filter_by(hash_duplicado=hash_duplicado).first():
                    duplicados_encontrados += 1
                    duplicados_detalle.append({
                        'fecha': fecha_str,
                        'hora': hora.isoformat() if hora else None,
                        'tipo_movimiento': tipo_movimiento,
                        'descripcion': descripcion,
                        'importe': importe,
                        'categoria': categoria,
                        'tipo_juego': tipo_juego
                    })
                    continue
                
                # Calcular nivel de buy-in para torneos
                nivel_buyin = None
                if categoria == 'Torneo' and tipo_movimiento == 'Buy In':
                    nivel_buyin = clasificar_nivel_buyin(importe)
                
                # Crear registro
                nuevo_resultado = PokerResult(
                    fecha=fecha,
                    hora=hora,
                    tipo_movimiento=tipo_movimiento,
                    descripcion=descripcion,
                    importe=importe,
                    categoria=categoria,
                    tipo_juego=tipo_juego,
                    nivel_buyin=nivel_buyin,
                    sala='Pokerstars',
                    hash_duplicado=hash_duplicado
                )
                
                db.session.add(nuevo_resultado)
                resultados_importados += 1
                
            except Exception as e:
                print(f"Error procesando fila {index}: {e}")
                continue
        
        db.session.commit()
        
        # Ejecutar reclasificación automática de niveles de buy-in
        print(f"\n=== RECLASIFICACIÓN AUTOMÁTICA DE NIVELES DE BUY-IN ===")
        try:
            reclasificados = reclasificar_niveles_buyin_automatica()
            print(f"Registros reclasificados automáticamente: {reclasificados}")
        except Exception as e:
            print(f"Error en reclasificación automática: {e}")
        
        # Ejecutar reclasificación automática de tipos de juego
        print(f"\n=== RECLASIFICACIÓN AUTOMÁTICA DE TIPOS DE JUEGO ===")
        try:
            tipos_reclasificados = reclasificar_tipos_juego_automatica()
            print(f"Tipos de juego reclasificados automáticamente: {tipos_reclasificados}")
        except Exception as e:
            print(f"Error en reclasificación de tipos de juego: {e}")
        
        return resultados_importados, duplicados_encontrados, duplicados_detalle
        
    except Exception as e:
        db.session.rollback()
        raise Exception(f"Error procesando archivo Pokerstars: {str(e)}")

def categorizar_movimiento_pokerstars(action, game, tournament_id):
    """Categoriza movimientos específicos de Pokerstars"""
    
    # Mapeo de acciones de Pokerstars
    action_lower = action.lower()
    game_lower = game.lower() if game else ''
    
    # Determinar categoría
    if 'tournament' in action_lower or 'bounty' in action_lower:
        categoria = 'Torneo'
    elif 'chest reward' in action_lower:
        categoria = 'Bonus'
    elif 'cash' in action_lower or 'table buy in' in action_lower or 'table rebuy' in action_lower or 'leave table' in action_lower or 'table buy in (zoom)' in action_lower or 'leave table (zoom)' in action_lower:
        categoria = 'Cash'
    elif 'transfer' in action_lower:
        categoria = 'Transferencia'
    elif 'withdrawal' in action_lower:
        categoria = 'Retiro'
    elif 'deposit' in action_lower:
        categoria = 'Depósito'
    else:
        categoria = 'Otro'
    
    # Determinar tipo de movimiento
    if 'registration' in action_lower:
        tipo_movimiento = 'Buy In'
    elif 're-entry' in action_lower:
        tipo_movimiento = 'Reentry Buy In'
    elif 'payout' in action_lower or 'won' in action_lower:
        tipo_movimiento = 'Winnings'
    elif 'bounty' in action_lower:
        tipo_movimiento = 'Bounty'
    elif 'ticket' in action_lower:
        tipo_movimiento = 'Ticket'
    elif 'transfer' in action_lower:
        tipo_movimiento = 'Transferencia'
    elif 'withdrawal' in action_lower:
        tipo_movimiento = 'Retiro'
    else:
        tipo_movimiento = action
    
    # Determinar tipo de juego - priorizar información de la columna Game
    if game and game.strip():
        # Si hay información en la columna Game, usarla para determinar el tipo
        # Detectar Courchevel ANTES que PLO genérico
        if 'courchevel' in game_lower:
            tipo_juego = 'PL Courchevel Hi/Lo'
        elif 'plo' in game_lower or 'omaha' in game_lower:
            if 'hi/lo' in game_lower or 'hi lo' in game_lower:
                tipo_juego = 'PLO Hi/Lo'
            elif '8' in game_lower:
                tipo_juego = 'PLO8'
            else:
                tipo_juego = 'PLO'
        elif 'holdem' in game_lower or 'nlh' in game_lower or 'nl hold' in game_lower:
            tipo_juego = 'NLH'
        elif 'stud' in game_lower:
            tipo_juego = 'Stud'
        else:
            # Si hay información en Game pero no coincide con patrones conocidos
            if 'tournament' in action_lower or 'bounty' in action_lower:
                tipo_juego = 'Torneo'
            else:
                tipo_juego = 'Cash'
    elif 'tournament' in action_lower or 'bounty' in action_lower:
        # Si no hay información en Game pero es un torneo, usar 'Torneo'
        tipo_juego = 'Torneo'
    else:
        tipo_juego = 'Cash'
    
    return categoria, tipo_movimiento, tipo_juego

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/importar')
def importar():
    return render_template('importar.html')

@app.route('/informes')
def informes():
    return render_template('informes.html')

@app.route('/analisis')
def analisis():
    return render_template('analisis.html')

@app.route('/api/importar', methods=['POST'])
def api_importar():
    if 'archivo' not in request.files:
        return jsonify({'error': 'No se seleccionó ningún archivo'}), 400
    
    archivo = request.files['archivo']
    sala = request.form.get('sala')
    
    if archivo.filename == '':
        return jsonify({'error': 'No se seleccionó ningún archivo'}), 400
    
    if not sala:
        return jsonify({'error': 'Debe seleccionar una sala'}), 400
    
    if archivo and archivo.filename.endswith(('.xlsx', '.xls')):
        filename = secure_filename(archivo.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        archivo.save(filepath)
        
        try:
            # Procesar el archivo según la sala
            resultados_importados = 0
            duplicados_encontrados = 0
            
            if sala == 'WPN':
                resultados_importados, duplicados_encontrados, duplicados_detalle = procesar_archivo_wpn(filepath)
            elif sala == 'Pokerstars':
                resultados_importados, duplicados_encontrados, duplicados_detalle = procesar_archivo_pokerstars(filepath)
            
            # Mover archivo a carpeta procesados
            import shutil
            from datetime import datetime
            
            # Crear nombre único para el archivo procesado
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            nombre_archivo = f"{timestamp}_{filename}"
            ruta_procesados = os.path.join('procesados', nombre_archivo)
            
            # Mover archivo
            shutil.move(filepath, ruta_procesados)
            print(f"Archivo movido a: {ruta_procesados}")
            
            # Crear mensaje detallado
            mensaje = f'Archivo importado exitosamente. {resultados_importados} registros importados, {duplicados_encontrados} duplicados omitidos.'
            
            return jsonify({
                'mensaje': mensaje,
                'resultados_importados': resultados_importados,
                'duplicados_encontrados': duplicados_encontrados,
                'duplicados_detalle': duplicados_detalle
            })
            
        except Exception as e:
            return jsonify({'error': f'Error al procesar el archivo: {str(e)}'}), 500
        finally:
            # Limpiar archivo temporal
            if os.path.exists(filepath):
                os.remove(filepath)
    
    return jsonify({'error': 'Formato de archivo no válido'}), 400

@app.route('/api/informes/resultados', methods=['GET'])
def api_informes_resultados():
    fecha_inicio = request.args.get('fecha_inicio')
    fecha_fin = request.args.get('fecha_fin')
    tipo_movimiento = request.args.get('tipo_movimiento')
    monto_minimo = request.args.get('monto_minimo', type=float)
    
    # Nuevos filtros para categoría, tipo de juego, nivel de buy-in y sala
    categorias = request.args.getlist('categorias[]')
    tipos_juego = request.args.getlist('tipos_juego[]')
    niveles_buyin = request.args.getlist('niveles_buyin[]')
    salas = request.args.getlist('salas[]')
    
    query = PokerResult.query
    
    if fecha_inicio:
        query = query.filter(PokerResult.fecha >= datetime.strptime(fecha_inicio, '%Y-%m-%d').date())
    if fecha_fin:
        query = query.filter(PokerResult.fecha <= datetime.strptime(fecha_fin, '%Y-%m-%d').date())
    if tipo_movimiento:
        query = query.filter(PokerResult.tipo_movimiento == tipo_movimiento)
    if monto_minimo is not None:
        query = query.filter(PokerResult.importe >= monto_minimo)
    
    # Aplicar filtros de categoría (selección múltiple)
    if categorias:
        query = query.filter(PokerResult.categoria.in_(categorias))
    
    # Aplicar filtros de tipo de juego (selección múltiple)
    if tipos_juego:
        query = query.filter(PokerResult.tipo_juego.in_(tipos_juego))
    
    # Aplicar filtros de nivel de buy-in (selección múltiple)
    if niveles_buyin:
        query = query.filter(PokerResult.nivel_buyin.in_(niveles_buyin))
    
    # Aplicar filtros de sala (selección múltiple)
    if salas:
        query = query.filter(PokerResult.sala.in_(salas))
    
    resultados = query.all()
    
    # Calcular estadísticas
    # Contar torneos jugados: tipo_movimiento = "Buy In" y categoria = "Torneo"
    cantidad_torneos = len([r for r in resultados if r.tipo_movimiento == 'Buy In' and r.categoria == 'Torneo'])
    
    # Calcular estadísticas específicas de torneos
    torneos = [r for r in resultados if r.categoria == 'Torneo']
    
    # Total invertido: suma de todos los egresos (importes negativos) de torneos
    total_invertido = sum(abs(r.importe) for r in torneos if r.importe < 0)
    
    # Total de ganancias: suma de todos los ingresos (importes positivos) de torneos
    total_ganancias = sum(r.importe for r in torneos if r.importe > 0)
    
    # Calcular ROI: (ganancias - invertido) / invertido
    roi = 0
    if total_invertido > 0:
        roi = ((total_ganancias - total_invertido) / total_invertido) * 100
    
    # Resultado económico excluyendo transferencias, retiros y depósitos
    movimientos_poker = [r for r in resultados if r.categoria not in ['Transferencia', 'Depósito', 'Retiro'] and r.tipo_movimiento not in ['Retiro']]
    resultado_economico = sum(r.importe for r in movimientos_poker)
    
    # Suma total de todos los importes (incluyendo todos los registros filtrados)
    suma_importes = sum(r.importe for r in resultados)
    
    # Calcular resultados diarios de los últimos 10 días (SIN FILTROS)
    from datetime import timedelta
    
    # Obtener los últimos 10 días calendario
    hoy = datetime.now().date()
    ultimos_10_dias = [hoy - timedelta(days=i) for i in range(10)]
    ultimos_10_dias.reverse()  # Ordenar de más antiguo a más reciente
    
    # Obtener TODOS los movimientos de poker (sin filtros) para el gráfico
    todos_movimientos_poker = PokerResult.query.filter(
        PokerResult.categoria.notin_(['Transferencia', 'Depósito']),
        PokerResult.tipo_movimiento.notin_(['Retiro'])
    ).all()
    
    # Calcular resultado por día
    resultados_diarios = []
    for fecha in ultimos_10_dias:
        # Filtrar movimientos de poker para esta fecha (sin otros filtros)
        movimientos_dia = [r for r in todos_movimientos_poker if r.fecha == fecha]
        resultado_dia = sum(r.importe for r in movimientos_dia)
        resultados_diarios.append({
            'fecha': fecha.isoformat(),
            'resultado': resultado_dia,
            'movimientos': len(movimientos_dia)
        })
    
    return jsonify({
        'resultados': [{
            'fecha': r.fecha.isoformat(),
            'hora': r.hora.isoformat() if r.hora else None,
            'tipo_movimiento': r.tipo_movimiento,
            'descripcion': r.descripcion,
            'importe': r.importe,
            'categoria': r.categoria,
            'tipo_juego': r.tipo_juego,
            'nivel_buyin': r.nivel_buyin,
            'sala': r.sala
        } for r in resultados],
        'estadisticas': {
            'cantidad_torneos': cantidad_torneos,
            'total_registros': len(resultados),
            'suma_importes': suma_importes,
            'total_invertido': total_invertido,
            'total_ganancias': total_ganancias,
            'roi': roi,
            'resultado_economico': resultado_economico
        },
        'resultados_diarios': resultados_diarios
    })

@app.route('/api/informes/opciones', methods=['GET'])
def api_informes_opciones():
    """Obtiene las opciones disponibles para los filtros"""
    # Obtener categorías únicas
    categorias = db.session.query(PokerResult.categoria).distinct().all()
    categorias = [cat[0] for cat in categorias if cat[0]]
    
    # Obtener tipos de juego únicos
    tipos_juego = db.session.query(PokerResult.tipo_juego).distinct().all()
    tipos_juego = [tipo[0] for tipo in tipos_juego if tipo[0]]
    
    # Obtener tipos de movimiento únicos
    tipos_movimiento = db.session.query(PokerResult.tipo_movimiento).distinct().all()
    tipos_movimiento = [tipo[0] for tipo in tipos_movimiento if tipo[0]]
    
    # Obtener niveles de buy-in únicos
    niveles_buyin = db.session.query(PokerResult.nivel_buyin).distinct().all()
    niveles_buyin = [nivel[0] for nivel in niveles_buyin if nivel[0]]
    
    # Obtener salas únicas
    salas = db.session.query(PokerResult.sala).distinct().all()
    salas = [sala[0] for sala in salas if sala[0]]
    
    return jsonify({
        'categorias': sorted(categorias),
        'tipos_juego': sorted(tipos_juego),
        'tipos_movimiento': sorted(tipos_movimiento),
        'niveles_buyin': sorted(niveles_buyin),
        'salas': sorted(salas)
    })

@app.route('/api/analisis/insights', methods=['GET'])
def api_analisis_insights():
    """Análisis avanzado con insights para gestión del juego"""
    try:
        # Obtener todos los registros de torneos
        torneos = PokerResult.query.filter(PokerResult.categoria == 'Torneo').all()
        
        if not torneos:
            return jsonify({'error': 'No hay datos de torneos para analizar'}), 400
        
        # Análisis por nivel de buy-in
        analisis_buyin = analizar_rendimiento_por_buyin(torneos)
        
        # Análisis por sala
        analisis_sala = analizar_rendimiento_por_sala(torneos)
        
        # Análisis temporal
        analisis_temporal = analizar_patrones_temporales(torneos)
        
        # Análisis por tipo de juego
        analisis_juego = analizar_rendimiento_por_juego(torneos)
        
        # Análisis de consistencia
        analisis_consistencia = analizar_consistencia_jugador(torneos)
        
        # Recomendaciones estratégicas
        recomendaciones = generar_recomendaciones(analisis_buyin, analisis_temporal, analisis_juego, analisis_consistencia)
        
        return jsonify({
            'analisis_buyin': analisis_buyin,
            'analisis_sala': analisis_sala,
            'analisis_temporal': analisis_temporal,
            'analisis_juego': analisis_juego,
            'analisis_consistencia': analisis_consistencia,
            'recomendaciones': recomendaciones
        })
        
    except Exception as e:
        return jsonify({'error': f'Error en análisis: {str(e)}'}), 500

def analizar_rendimiento_por_buyin(torneos):
    """Analiza el rendimiento por nivel de buy-in"""
    buyin_stats = {}
    
    for torneo in torneos:
        if torneo.nivel_buyin:
            if torneo.nivel_buyin not in buyin_stats:
                buyin_stats[torneo.nivel_buyin] = {
                    'total_torneos': 0,
                    'total_invertido': 0,
                    'total_ganancias': 0,
                    'roi': 0,
                    'mejor_racha': 0,
                    'peor_racha': 0,
                    'racha_actual': 0,
                    'salas': set()  # Agregar información de salas
                }
            
            buyin_stats[torneo.nivel_buyin]['total_torneos'] += 1
            buyin_stats[torneo.nivel_buyin]['total_invertido'] += abs(torneo.importe) if torneo.importe < 0 else 0
            buyin_stats[torneo.nivel_buyin]['total_ganancias'] += torneo.importe if torneo.importe > 0 else 0
            buyin_stats[torneo.nivel_buyin]['salas'].add(torneo.sala)
    
    # Calcular ROI y rachas
    for nivel, stats in buyin_stats.items():
        if stats['total_invertido'] > 0:
            stats['roi'] = ((stats['total_ganancias'] - stats['total_invertido']) / stats['total_invertido']) * 100
        
        # Calcular rachas (simplificado)
        stats['mejor_racha'] = max(0, stats['total_ganancias'] / stats['total_invertido'] if stats['total_invertido'] > 0 else 0)
        stats['peor_racha'] = min(0, (stats['total_ganancias'] - stats['total_invertido']) / stats['total_invertido'] if stats['total_invertido'] > 0 else 0)
        
        # Convertir set a lista para JSON
        stats['salas'] = list(stats['salas'])
    
    return buyin_stats

def analizar_rendimiento_por_sala(torneos):
    """Analiza el rendimiento por sala"""
    sala_stats = {}
    
    for torneo in torneos:
        if torneo.sala:
            if torneo.sala not in sala_stats:
                sala_stats[torneo.sala] = {
                    'total_torneos': 0,
                    'total_invertido': 0,
                    'total_ganancias': 0,
                    'roi': 0,
                    'torneos_ganados': 0,
                    'tipos_juego': set(),
                    'niveles_buyin': set()
                }
            
            sala_stats[torneo.sala]['total_torneos'] += 1
            sala_stats[torneo.sala]['total_invertido'] += abs(torneo.importe) if torneo.importe < 0 else 0
            sala_stats[torneo.sala]['total_ganancias'] += torneo.importe if torneo.importe > 0 else 0
            
            if torneo.importe > 0:
                sala_stats[torneo.sala]['torneos_ganados'] += 1
            
            if torneo.tipo_juego:
                sala_stats[torneo.sala]['tipos_juego'].add(torneo.tipo_juego)
            
            if torneo.nivel_buyin:
                sala_stats[torneo.sala]['niveles_buyin'].add(torneo.nivel_buyin)
    
    # Calcular ROI y porcentaje de victorias
    for sala, stats in sala_stats.items():
        if stats['total_invertido'] > 0:
            stats['roi'] = ((stats['total_ganancias'] - stats['total_invertido']) / stats['total_invertido']) * 100
        
        if stats['total_torneos'] > 0:
            stats['porcentaje_victorias'] = (stats['torneos_ganados'] / stats['total_torneos']) * 100
        
        # Convertir sets a listas para JSON
        stats['tipos_juego'] = list(stats['tipos_juego'])
        stats['niveles_buyin'] = list(stats['niveles_buyin'])
    
    return sala_stats

def analizar_patrones_temporales(torneos):
    """Analiza patrones temporales de juego"""
    from collections import defaultdict
    import datetime
    
    # Agrupar por día de la semana
    dias_semana = defaultdict(lambda: {'torneos': 0, 'resultado': 0})
    dias_nombres = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    
    # Agrupar por hora del día
    horas_dia = defaultdict(lambda: {'torneos': 0, 'resultado': 0})
    
    for torneo in torneos:
        if torneo.fecha:
            dia_semana = torneo.fecha.weekday()
            dias_semana[dia_semana]['torneos'] += 1
            dias_semana[dia_semana]['resultado'] += torneo.importe
            
            if torneo.hora:
                hora = torneo.hora.hour
                horas_dia[hora]['torneos'] += 1
                horas_dia[hora]['resultado'] += torneo.importe
    
    # Procesar datos
    patrones_dias = []
    for i, dia in enumerate(dias_nombres):
        if i in dias_semana:
            patrones_dias.append({
                'dia': dia,
                'torneos': dias_semana[i]['torneos'],
                'resultado_promedio': dias_semana[i]['resultado'] / dias_semana[i]['torneos'] if dias_semana[i]['torneos'] > 0 else 0
            })
    
    patrones_horas = []
    for hora in sorted(horas_dia.keys()):
        patrones_horas.append({
            'hora': f"{hora:02d}:00",
            'torneos': horas_dia[hora]['torneos'],
            'resultado_promedio': horas_dia[hora]['resultado'] / horas_dia[hora]['torneos'] if horas_dia[hora]['torneos'] > 0 else 0
        })
    
    return {
        'por_dia_semana': patrones_dias,
        'por_hora': patrones_horas
    }

def analizar_rendimiento_por_juego(torneos):
    """Analiza el rendimiento por tipo de juego"""
    juego_stats = {}
    
    for torneo in torneos:
        if torneo.tipo_juego:
            if torneo.tipo_juego not in juego_stats:
                juego_stats[torneo.tipo_juego] = {
                    'total_torneos': 0,
                    'total_invertido': 0,
                    'total_ganancias': 0,
                    'roi': 0,
                    'torneos_ganados': 0
                }
            
            juego_stats[torneo.tipo_juego]['total_torneos'] += 1
            juego_stats[torneo.tipo_juego]['total_invertido'] += abs(torneo.importe) if torneo.importe < 0 else 0
            juego_stats[torneo.tipo_juego]['total_ganancias'] += torneo.importe if torneo.importe > 0 else 0
            
            if torneo.importe > 0:
                juego_stats[torneo.tipo_juego]['torneos_ganados'] += 1
    
    # Calcular ROI y porcentaje de victorias
    for juego, stats in juego_stats.items():
        if stats['total_invertido'] > 0:
            stats['roi'] = ((stats['total_ganancias'] - stats['total_invertido']) / stats['total_invertido']) * 100
        
        if stats['total_torneos'] > 0:
            stats['porcentaje_victorias'] = (stats['torneos_ganados'] / stats['total_torneos']) * 100
    
    return juego_stats

def analizar_consistencia_jugador(torneos):
    """Analiza la consistencia del jugador"""
    from collections import defaultdict
    import statistics
    
    resultados_diarios = defaultdict(float)
    
    for torneo in torneos:
        if torneo.fecha:
            resultados_diarios[torneo.fecha] += torneo.importe
    
    resultados = list(resultados_diarios.values())
    
    if not resultados:
        return {'consistencia': 'Sin datos suficientes'}
    
    # Calcular métricas de consistencia
    media = statistics.mean(resultados)
    desviacion = statistics.stdev(resultados) if len(resultados) > 1 else 0
    coeficiente_variacion = (desviacion / abs(media)) * 100 if media != 0 else 0
    
    # Días positivos vs negativos
    dias_positivos = sum(1 for r in resultados if r > 0)
    dias_negativos = sum(1 for r in resultados if r < 0)
    dias_neutros = sum(1 for r in resultados if r == 0)
    
    return {
        'dias_jugados': len(resultados),
        'resultado_promedio_diario': media,
        'desviacion_estandar': desviacion,
        'coeficiente_variacion': coeficiente_variacion,
        'dias_positivos': dias_positivos,
        'dias_negativos': dias_negativos,
        'dias_neutros': dias_neutros,
        'consistencia': 'Alta' if coeficiente_variacion < 50 else 'Media' if coeficiente_variacion < 100 else 'Baja'
    }

def generar_recomendaciones(analisis_buyin, analisis_temporal, analisis_juego, analisis_consistencia):
    """Genera recomendaciones estratégicas basadas en el análisis"""
    recomendaciones = []
    
    # Recomendaciones por nivel de buy-in
    mejor_buyin = max(analisis_buyin.items(), key=lambda x: x[1]['roi']) if analisis_buyin else None
    peor_buyin = min(analisis_buyin.items(), key=lambda x: x[1]['roi']) if analisis_buyin else None
    
    if mejor_buyin and mejor_buyin[1]['roi'] > 0:
        recomendaciones.append({
            'tipo': 'buyin',
            'titulo': f'Mejor rendimiento en {mejor_buyin[0]}',
            'descripcion': f'Tu ROI en {mejor_buyin[0]} es del {mejor_buyin[1]["roi"]:.1f}%. Considera jugar más en este nivel.',
            'prioridad': 'alta'
        })
    
    if peor_buyin and peor_buyin[1]['roi'] < -20:
        recomendaciones.append({
            'tipo': 'buyin',
            'titulo': f'Revisar estrategia en {peor_buyin[0]}',
            'descripcion': f'Tu ROI en {peor_buyin[0]} es del {peor_buyin[1]["roi"]:.1f}%. Considera revisar tu estrategia o reducir la frecuencia.',
            'prioridad': 'alta'
        })
    
    # Recomendaciones por tipo de juego
    mejor_juego = max(analisis_juego.items(), key=lambda x: x[1]['roi']) if analisis_juego else None
    
    if mejor_juego and mejor_juego[1]['roi'] > 0:
        recomendaciones.append({
            'tipo': 'juego',
            'titulo': f'Fuerte en {mejor_juego[0]}',
            'descripcion': f'Tu ROI en {mejor_juego[0]} es del {mejor_juego[1]["roi"]:.1f}% con {mejor_juego[1]["porcentaje_victorias"]:.1f}% de victorias.',
            'prioridad': 'media'
        })
    
    # Recomendaciones temporales
    mejor_dia = max(analisis_temporal['por_dia_semana'], key=lambda x: x['resultado_promedio']) if analisis_temporal['por_dia_semana'] else None
    
    if mejor_dia and mejor_dia['resultado_promedio'] > 0:
        recomendaciones.append({
            'tipo': 'temporal',
            'titulo': f'Mejor día: {mejor_dia["dia"]}',
            'descripcion': f'Tu resultado promedio los {mejor_dia["dia"]}s es de ${mejor_dia["resultado_promedio"]:.2f}. Considera jugar más este día.',
            'prioridad': 'baja'
        })
    
    # Recomendaciones de consistencia
    if analisis_consistencia.get('consistencia') == 'Baja':
        recomendaciones.append({
            'tipo': 'consistencia',
            'titulo': 'Mejorar consistencia',
            'descripcion': 'Tu juego muestra alta variabilidad. Considera establecer límites de pérdida y ganancia diarios.',
            'prioridad': 'alta'
        })
    
    return recomendaciones

@app.route('/api/eliminar-todos', methods=['POST'])
def api_eliminar_todos():
    """Elimina todos los registros de la base de datos"""
    try:
        # Contar registros antes de eliminar
        total_registros = PokerResult.query.count()
        
        if total_registros == 0:
            return jsonify({
                'mensaje': 'No hay registros para eliminar',
                'registros_eliminados': 0
            })
        
        # Eliminar todos los registros
        PokerResult.query.delete()
        db.session.commit()
        
        return jsonify({
            'mensaje': f'Se eliminaron {total_registros} registros exitosamente',
            'registros_eliminados': total_registros
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al eliminar registros: {str(e)}'}), 500

@app.route('/api/eliminar-por-sala', methods=['POST'])
def api_eliminar_por_sala():
    """Elimina registros de una sala específica"""
    try:
        data = request.get_json()
        sala = data.get('sala')
        
        if not sala:
            return jsonify({'error': 'Sala no especificada'}), 400
        
        # Contar registros de la sala antes de eliminar
        registros_sala = PokerResult.query.filter_by(sala=sala).count()
        
        if registros_sala == 0:
            return jsonify({
                'mensaje': f'No se encontraron registros de la sala {sala}',
                'registros_eliminados': 0
            })
        
        # Eliminar registros de la sala
        PokerResult.query.filter_by(sala=sala).delete()
        db.session.commit()
        
        return jsonify({
            'mensaje': f'Se eliminaron {registros_sala} registros de la sala {sala}',
            'registros_eliminados': registros_sala,
            'sala': sala
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error al eliminar registros de la sala: {str(e)}'}), 500

@app.route('/api/salas-disponibles', methods=['GET'])
def api_salas_disponibles():
    """Obtiene las salas disponibles en la base de datos"""
    try:
        salas = db.session.query(PokerResult.sala).distinct().all()
        salas = [sala[0] for sala in salas if sala[0]]
        
        # Contar registros por sala
        salas_info = []
        for sala in salas:
            count = PokerResult.query.filter_by(sala=sala).count()
            salas_info.append({
                'sala': sala,
                'registros': count
            })
        
        return jsonify({
            'salas': salas_info
        })
        
    except Exception as e:
        return jsonify({'error': f'Error al obtener salas: {str(e)}'}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=9000)
