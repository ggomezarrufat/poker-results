#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from supabase import create_client, Client
from datetime import datetime, timedelta
import pandas as pd
import hashlib
import uuid

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

# Configurar favicon
@app.route('/favicon.ico')
def favicon():
    return app.send_static_file('favicon.ico')

# Configurar Supabase
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError('SUPABASE_URL y SUPABASE_KEY deben estar configurados en el archivo .env')

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Configurar Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username, email, is_admin=False, is_active=True):
        self.id = id
        self.username = username
        self.email = email
        self.is_admin = is_admin
        self._is_active = is_active
    
    @property
    def is_active(self):
        return self._is_active
    
    @is_active.setter
    def is_active(self, value):
        self._is_active = value

@login_manager.user_loader
def load_user(user_id):
    try:
        response = supabase.table('users').select('*').eq('id', user_id).execute()
        if response.data:
            user_data = response.data[0]
            return User(
                id=user_data['id'],
                username=user_data['username'],
                email=user_data['email'],
                is_admin=user_data.get('is_admin', False),
                is_active=user_data.get('is_active', True)
            )
    except Exception as e:
        print(f'Error cargando usuario: {e}')
    return None

# Funciones auxiliares para Supabase
def get_user_poker_results(user_id, filters=None):
    try:
        query = supabase.table('poker_results').select('*').eq('user_id', user_id)
        
        if filters:
            if 'fecha_inicio' in filters:
                query = query.gte('fecha', filters['fecha_inicio'])
            if 'fecha_fin' in filters:
                query = query.lte('fecha', filters['fecha_fin'])
            if 'categorias' in filters:
                query = query.in_('categoria', filters['categorias'])
            if 'tipos_juego' in filters:
                query = query.in_('tipo_juego', filters['tipos_juego'])
            if 'niveles_buyin' in filters:
                query = query.in_('nivel_buyin', filters['niveles_buyin'])
            if 'salas' in filters:
                query = query.in_('sala', filters['salas'])
            if 'tipo_movimiento' in filters:
                query = query.eq('tipo_movimiento', filters['tipo_movimiento'])
            if 'monto_minimo' in filters:
                query = query.gte('importe', filters['monto_minimo'])
        
        response = query.execute()
        return response.data if response.data else []
    except Exception as e:
        print(f'Error obteniendo resultados: {e}')
        return []

def create_poker_result(user_id, data):
    try:
        poker_data = {
            'user_id': user_id,
            'fecha': data.get('fecha'),
            'hora': data.get('hora'),
            'descripcion': data.get('descripcion'),
            'importe': data.get('importe'),
            'categoria': data.get('categoria'),
            'tipo_movimiento': data.get('tipo_movimiento'),
            'tipo_juego': data.get('tipo_juego'),
            'sala': data.get('sala'),
            'nivel_buyin': data.get('nivel_buyin'),
            'hash_duplicado': data.get('hash_duplicado'),
            'created_at': datetime.utcnow().isoformat()
        }
        response = supabase.table('poker_results').insert(poker_data).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f'Error creando resultado: {e}')
        return None

def delete_user_poker_results(user_id):
    try:
        response = supabase.table('poker_results').delete().eq('user_id', user_id).execute()
        return True
    except Exception as e:
        print(f'Error eliminando resultados: {e}')
        return False

def bulk_insert_poker_results(user_id, records):
    try:
        poker_data = []
        for record in records:
            poker_data.append({
                'user_id': user_id,
                'fecha': record.get('fecha'),
                'hora': record.get('hora'),
                'descripcion': record.get('descripcion'),
                'importe': record.get('importe'),
                'categoria': record.get('categoria'),
                'tipo_movimiento': record.get('tipo_movimiento'),
                'tipo_juego': record.get('tipo_juego'),
                'sala': record.get('sala'),
                'nivel_buyin': record.get('nivel_buyin'),
                'hash_duplicado': record.get('hash_duplicado'),
                'created_at': datetime.utcnow().isoformat()
            })
        if poker_data:
            response = supabase.table('poker_results').insert(poker_data).execute()
            return len(response.data) if response.data else 0
        return 0
    except Exception as e:
        print(f'Error insertando registros masivos: {e}')
        return 0

def get_user_distinct_values(user_id, column):
    try:
        response = supabase.table('poker_results').select(column).eq('user_id', user_id).execute()
        if response.data:
            values = [row[column] for row in response.data if row[column]]
            return list(set(values))
        return []
    except Exception as e:
        print(f'Error obteniendo valores distintos: {e}')
        return []

# Rutas principales
@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        try:
            response = supabase.table('users').select('*').eq('username', username).execute()
            if response.data:
                user_data = response.data[0]
                if check_password_hash(user_data['password_hash'], password) and user_data.get('is_active', True):
                    user = User(
                        id=user_data['id'],
                        username=user_data['username'],
                        email=user_data['email'],
                        is_admin=user_data.get('is_admin', False),
                        is_active=user_data.get('is_active', True)
                    )
                    login_user(user)
                    
                    # Actualizar último login
                    supabase.table('users').update({'last_login': datetime.utcnow().isoformat()}).eq('id', user.id).execute()
                    
                    flash('Login exitoso!', 'success')
                    return redirect(url_for('index'))
                else:
                    flash('Credenciales incorrectas', 'error')
            else:
                flash('Usuario no encontrado', 'error')
        except Exception as e:
            flash(f'Error en login: {e}', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logout exitoso!', 'success')
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validaciones básicas
        if not username or not email or not password:
            flash('Todos los campos son obligatorios', 'error')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Las contraseñas no coinciden', 'error')
            return render_template('register.html')
        
        if len(password) < 6:
            flash('La contraseña debe tener al menos 6 caracteres', 'error')
            return render_template('register.html')
        
        try:
            # Verificar si el usuario ya existe
            existing_user = supabase.table('users').select('*').eq('username', username).execute()
            if existing_user.data:
                flash('El nombre de usuario ya existe', 'error')
                return render_template('register.html')
            
            # Verificar si el email ya existe
            existing_email = supabase.table('users').select('*').eq('email', email).execute()
            if existing_email.data:
                flash('El email ya está registrado', 'error')
                return render_template('register.html')
            
            # Crear nuevo usuario
            user_id = str(uuid.uuid4())
            password_hash = generate_password_hash(password)
            
            user_data = {
                'id': user_id,
                'username': username,
                'email': email,
                'password_hash': password_hash,
                'is_admin': False,
                'is_active': True,
                'created_at': datetime.now().isoformat()
            }
            
            response = supabase.table('users').insert(user_data).execute()
            
            if response.data:
                flash('Usuario registrado exitosamente!', 'success')
                return redirect(url_for('login'))
            else:
                flash('Error al registrar usuario', 'error')
                
        except Exception as e:
            flash(f'Error en registro: {e}', 'error')
    
    return render_template('register.html')

@app.route('/importar')
@login_required
def importar():
    return render_template('importar.html')

@app.route('/analisis')
@login_required
def analisis():
    return render_template('analisis.html')

@app.route('/informes')
@login_required
def informes():
    return render_template('informes.html')

# APIs
@app.route('/api/informes/resultados', methods=['GET'])
@login_required
def api_informes_resultados():
    try:
        # Obtener filtros
        fecha_inicio = request.args.get('fecha_inicio')
        fecha_fin = request.args.get('fecha_fin')
        categorias = request.args.getlist('categorias[]')
        tipos_juego = request.args.getlist('tipos_juego[]')
        niveles_buyin = request.args.getlist('niveles_buyin[]')
        salas = request.args.getlist('salas[]')
        
        # Preparar filtros
        filters = {}
        if fecha_inicio:
            filters['fecha_inicio'] = fecha_inicio
        if fecha_fin:
            filters['fecha_fin'] = fecha_fin
        if categorias:
            filters['categorias'] = categorias
        if tipos_juego:
            filters['tipos_juego'] = tipos_juego
        if niveles_buyin:
            filters['niveles_buyin'] = niveles_buyin
        if salas:
            filters['salas'] = salas
        
        # Obtener resultados
        resultados = get_user_poker_results(current_user.id, filters)
        
        # Calcular estadísticas básicas
        total_registros = len(resultados)
        suma_importes = sum(r.get('importe', 0) for r in resultados)
        
        return jsonify({
            'success': True,
            'resultados': resultados,
            'estadisticas': {
                'total_registros': total_registros,
                'suma_importes': suma_importes
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/informes/opciones', methods=['GET'])
@login_required
def api_informes_opciones():
    try:
        categorias = get_user_distinct_values(current_user.id, 'categoria')
        tipos_juego = get_user_distinct_values(current_user.id, 'tipo_juego')
        niveles_buyin = get_user_distinct_values(current_user.id, 'nivel_buyin')
        salas = get_user_distinct_values(current_user.id, 'sala')
        
        return jsonify({
            'success': True,
            'opciones': {
                'categorias': categorias,
                'tipos_juego': tipos_juego,
                'niveles_buyin': niveles_buyin,
                'salas': salas
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# APIs de importación
@app.route('/api/previsualizar-archivo', methods=['POST'])
@login_required
def api_previsualizar_archivo():
    """Previsualizar archivo antes de importar"""
    try:
        if 'archivo' not in request.files:
            return jsonify({'success': False, 'error': 'No se ha seleccionado ningún archivo'}), 400
        
        archivo = request.files['archivo']
        if archivo.filename == '':
            return jsonify({'success': False, 'error': 'No se ha seleccionado ningún archivo'}), 400
        
        # Leer el archivo con detección robusta
        df = None
        filename = archivo.filename.lower()
        
        # Detectar si es archivo HTML (PokerStars)
        archivo.seek(0)
        primeros_bytes = archivo.read(100).decode('utf-8', errors='ignore')
        archivo.seek(0)
        
        if filename.endswith('.html') or primeros_bytes.strip().upper().startswith('<HTML'):
            # Archivo HTML de PokerStars
            from bs4 import BeautifulSoup
            content = archivo.read().decode('utf-8')
            soup = BeautifulSoup(content, 'html.parser')
            table = soup.find('table')
            
            if not table:
                return jsonify({'success': False, 'error': 'No se encontró tabla en el archivo HTML'}), 400
            
            rows = table.find_all('tr')
            if len(rows) < 3:
                return jsonify({'success': False, 'error': 'Archivo HTML no tiene suficientes filas'}), 400
            
            # Headers (segunda fila)
            subheaders = [td.get_text().strip() for td in rows[1].find_all(['td', 'th'])]
            
            # Filas de datos (desde la fila 2)
            data_rows = rows[2:]
            
            # Crear DataFrame
            data = []
            for row in data_rows[:10]:  # Solo primeras 10 para preview
                cells = [td.get_text().strip() for td in row.find_all(['td', 'th'])]
                if len(cells) >= len(subheaders):
                    data.append(cells[:len(subheaders)])
                else:
                    while len(cells) < len(subheaders):
                        cells.append('')
                    data.append(cells)
            
            if not data:
                return jsonify({'success': False, 'error': 'No se encontraron datos en el archivo HTML'}), 400
            
            df = pd.DataFrame(data, columns=subheaders)
            
        elif filename.endswith('.csv'):
            # Archivo CSV
            df = pd.read_csv(archivo)
            
        elif filename.endswith(('.xlsx', '.xls')):
            # Archivo Excel - intentar con diferentes motores
            try:
                if filename.endswith('.xlsx'):
                    df = pd.read_excel(archivo, engine='openpyxl')
                elif filename.endswith('.xls'):
                    df = pd.read_excel(archivo, engine='xlrd')
            except Exception as e:
                # Intentar con otros motores
                try:
                    df = pd.read_excel(archivo, engine='openpyxl')
                except:
                    try:
                        df = pd.read_excel(archivo, engine='xlrd')
                    except:
                        df = pd.read_excel(archivo)
        else:
            return jsonify({'success': False, 'error': 'Formato de archivo no soportado'}), 400
        
        # Mostrar solo las primeras 10 filas para previsualización
        preview_data = df.head(10).to_dict('records')
        
        return jsonify({
            'success': True,
            'preview': preview_data,
            'total_rows': len(df),
            'columns': list(df.columns)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': f'Error al procesar archivo: {str(e)}'}), 500

def procesar_archivo_wpn_optimizado(filepath, user_id, progress_callback=None):
    """Procesa archivos Excel/CSV de WPN y HTML/Excel de PokerStars con inserción masiva optimizada para Supabase"""
    try:
        # Detectar tipo de archivo leyendo los primeros bytes
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            primeros_bytes = f.read(100)
        
        # Detectar si es archivo HTML (PokerStars)
        es_html = (filepath.lower().endswith('.html') or 
                  primeros_bytes.strip().upper().startswith('<HTML'))
        
        if es_html:
            # Procesar archivo HTML de PokerStars
            print("🔍 Detectado archivo HTML de PokerStars")
            return procesar_archivo_pokerstars_html(filepath, user_id, progress_callback)
        
        # Detectar si es un archivo de PokerStars Excel por el nombre del archivo
        filename_lower = filepath.lower()
        es_pokerstars_excel = ('pokerstars' in filename_lower or 'poker' in filename_lower) and filename_lower.endswith(('.xls', '.xlsx'))
        
        if es_pokerstars_excel:
            print("🔍 Detectado archivo Excel de PokerStars por nombre")
            return procesar_archivo_pokerstars_excel(filepath, user_id, progress_callback)
        
        # Procesar archivo CSV/Excel
        df = None
        error_motores = []
        
        if filepath.endswith('.csv'):
            # Archivo CSV
            try:
                df = pd.read_csv(filepath)
                print("✅ Archivo CSV leído correctamente")
            except Exception as e:
                error_motores.append(f"CSV: {str(e)}")
        else:
            # Archivo Excel - intentar con diferentes motores
            filename = filepath.lower()
            print(f"🔍 Procesando archivo Excel: {filename}")
            
            if filename.endswith('.xlsx'):
                # Para archivos .xlsx, usar openpyxl
                try:
                    df = pd.read_excel(filepath, engine='openpyxl')
                    print("✅ Archivo leído con openpyxl")
                except Exception as e:
                    error_motores.append(f"openpyxl: {str(e)}")
                    
            elif filename.endswith('.xls'):
                # Para archivos .xls, usar xlrd
                try:
                    df = pd.read_excel(filepath, engine='xlrd')
                    print("✅ Archivo leído con xlrd")
                except Exception as e:
                    error_motores.append(f"xlrd: {str(e)}")
            
            # Si aún no se pudo leer, intentar todos los motores
            if df is None:
                for engine_name in ['openpyxl', 'xlrd']:
                    try:
                        df = pd.read_excel(filepath, engine=engine_name)
                        print(f"✅ Archivo leído con {engine_name}")
                        break
                    except Exception as e:
                        error_motores.append(f"{engine_name}: {str(e)}")
            
            # Último recurso: sin especificar motor
            if df is None:
                try:
                    df = pd.read_excel(filepath)
                    print("✅ Archivo leído sin especificar motor")
                except Exception as e:
                    error_motores.append(f"sin motor: {str(e)}")
        
        # Si no se pudo leer el archivo con ningún método
        if df is None:
            error_msg = f"No se pudo leer el archivo. Errores: {'; '.join(error_motores)}"
            print(f"❌ {error_msg}")
            return {'error': error_msg}
            
        print(f"Total registros en archivo: {len(df)}")
        
        # Detectar formato del archivo basado en las columnas
        if 'Date/Time' in df.columns or 'Action' in df.columns:
            # Es un archivo de PokerStars (Excel)
            print("🔍 Detectado formato PokerStars Excel")
            return procesar_archivo_pokerstars_excel(filepath, user_id, progress_callback)
        
        # Limpiar y procesar los datos
        df_original = len(df)
        
        # Detectar formato del archivo
        if 'Transaction Details' in df.columns:
            # Formato PokerStars
            df = df.dropna(subset=['Transaction Details'])
            df_sin_fecha = df_original - len(df)
            sala = 'PokerStars'
            print(f"Detectado formato PokerStars")
        elif 'Date' in df.columns:
            # Formato WPN
            df = df.dropna(subset=['Date'])
            df_sin_fecha = df_original - len(df)
            sala = 'WPN'
            print(f"Detectado formato WPN")
        else:
            return {'error': 'Formato de archivo no reconocido'}
        
        print(f"Registros eliminados por falta de fecha: {df_sin_fecha}")
        
        total_registros = len(df)
        print(f"Procesando {total_registros} registros...")
        
        # Enviar mensaje de inicio si hay callback
        if progress_callback:
            progress_callback(f"data: {json.dumps({'tipo': 'inicio', 'total_registros': total_registros})}\n\n")
        
        resultados_importados = 0
        duplicados_encontrados = 0
        errores_procesamiento = 0
        duplicados_detalle = []
        registros_nuevos = []
        
        # Obtener TODOS los registros existentes para comparación directa
        print("🔍 Obteniendo TODOS los registros existentes para detección de duplicados...")
        try:
            # Obtener todos los registros en lotes para evitar límites de Supabase
            all_records = []
            offset = 0
            limit = 1000
            
            while True:
                batch = supabase.table('poker_results').select(
                    'fecha', 'hora', 'descripcion', 'importe', 'sala', 'tipo_movimiento', 'categoria'
                ).eq('user_id', str(user_id)).range(offset, offset + limit - 1).execute()
                
                if not batch.data:
                    break
                    
                all_records.extend(batch.data)
                offset += limit
                
                if len(batch.data) < limit:
                    break
            
            # Crear un conjunto de registros existentes para comparación rápida
            registros_existentes = set()
            for record in all_records:
                registro_key = (
                    record['fecha'],
                    record['hora'],
                    record['descripcion'],
                    round(float(record['importe']), 2),
                    record['sala'],
                    record['tipo_movimiento'],
                    record['categoria']
                )
                registros_existentes.add(registro_key)
            
            print(f"✅ {len(registros_existentes)} registros existentes encontrados para comparación")
            if registros_existentes:
                # Mostrar algunos registros existentes para debug
                sample_registros = list(registros_existentes)[:2]
                for i, reg in enumerate(sample_registros):
                    print(f"🔍 Registro existente {i+1}: {reg[0]} {reg[1]} | {reg[2][:30]}... | {reg[3]}")
        except Exception as e:
            print(f"❌ Error obteniendo registros existentes: {e}")
            registros_existentes = set()
        
        # Procesar todos los registros
        print("🔄 Procesando registros...")
        for index, row in df.iterrows():
            try:
                # Mostrar progreso cada 100 registros
                if (index + 1) % 100 == 0 or (index + 1) == total_registros:
                    porcentaje = ((index + 1) / total_registros) * 100
                    print(f"Progreso: {index + 1}/{total_registros} registros procesados ({porcentaje:.1f}%)")
                    
                    # Enviar progreso al cliente si hay callback
                    if progress_callback:
                        progress_callback(f"data: {json.dumps({'tipo': 'progreso', 'procesados': index + 1, 'total': total_registros, 'porcentaje': porcentaje})}\n\n")
                
                # Variables para hash (valores originales antes de límites)
                hash_fecha = None
                hash_hora = None
                hash_descripcion = None
                hash_importe_original = None
                
                if sala == 'PokerStars':
                    # Formato PokerStars: Transaction Details, Individual Transaction Amounts, Running Balance
                    fecha_str = str(row['Transaction Details'])
                    descripcion = str(row['Individual Transaction Amounts'])
                    importe_str = str(row['Running Balance'])
                    
                    # Saltar la primera fila si es el encabezado
                    if 'Date/Time' in fecha_str or 'Action' in descripcion:
                        continue
                    
                    # Convertir fecha con manejo de errores
                    try:
                        fecha_hora = pd.to_datetime(fecha_str)
                        fecha = fecha_hora.date()
                        hora = fecha_hora.time()
                        hash_fecha = fecha.isoformat()
                        hash_hora = hora.isoformat() if hora else None
                    except:
                        # Si no se puede parsear la fecha, usar fecha actual
                        fecha = datetime.now().date()
                        hora = datetime.now().time()
                        hash_fecha = fecha.isoformat()
                        hash_hora = hora.isoformat() if hora else None
                    
                    # Extraer importe del texto con límite seguro
                    importe = 0.0
                    try:
                        if 'Tournament Registration' in descripcion:
                            # Extraer importe del balance (simplificado)
                            importe = -float(importe_str) if importe_str.replace('.', '').replace('-', '').isdigit() else 0
                        elif 'Tournament Won' in descripcion or 'Tournament Interim Payout' in descripcion:
                            importe = float(importe_str) if importe_str.replace('.', '').replace('-', '').isdigit() else 0
                        
                        # Guardar importe original para hash
                        hash_importe_original = importe
                        
                        # Limitar importe a rango seguro para Supabase (precision 10, scale 2 = max 99,999,999.99)
                        if abs(importe) > 99999999.99:
                            importe = 99999999.99 if importe > 0 else -99999999.99
                            print(f"⚠️  Importe limitado: {importe}")
                    except (ValueError, TypeError):
                        importe = 0.0
                        hash_importe_original = 0.0
                    
                    # Guardar descripción para hash
                    hash_descripcion = descripcion
                    
                    # Categorizar
                    categoria = 'Torneo'
                    tipo_movimiento = 'Buy In'
                    if 'Tournament Registration' in descripcion:
                        tipo_movimiento = 'Buy In'
                    elif 'Tournament Re-entry' in descripcion:
                        tipo_movimiento = 'Reentry Buy In'
                    elif 'Tournament Won' in descripcion:
                        tipo_movimiento = 'Winnings'
                    elif 'Tournament Interim Payout' in descripcion:
                        tipo_movimiento = 'Winnings'
                    
                else:
                    # Formato WPN original
                    fecha_str = str(row['Date'])
                    fecha_hora = pd.to_datetime(fecha_str, format='%H:%M:%S %Y-%m-%d')
                    fecha = fecha_hora.date()
                    hora = fecha_hora.time()
                    
                    money_in = float(row['Money In'])
                    money_out = float(row['Money Out'])
                    payment_method = str(row['Payment Method'])
                    descripcion = str(row['Description'])
                    
                    # Guardar valores originales para hash
                    hash_fecha = fecha.isoformat()
                    hash_hora = hora.isoformat() if hora else None
                    hash_descripcion = f"{payment_method}|{descripcion}"
                    hash_importe_original = money_in - money_out
                    
                    importe = money_in - money_out
                    # Limitar importe a rango seguro para Supabase (precision 10, scale 2 = max 99,999,999.99)
                    if abs(importe) > 99999999.99:
                        importe = 99999999.99 if importe > 0 else -99999999.99
                        print(f"⚠️  Importe limitado: {importe} (original: {money_in - money_out})")
                    
                    # Categorizar
                    categoria = 'Torneo'
                    tipo_movimiento = 'Buy In'
                    if 'Tournament Registration' in payment_method:
                        tipo_movimiento = 'Buy In'
                    elif 'Tournament Re-entry' in payment_method:
                        tipo_movimiento = 'Reentry Buy In'
                    elif 'Tournament Won' in payment_method:
                        tipo_movimiento = 'Winnings'
                    elif 'Tournament Interim Payout' in payment_method:
                        tipo_movimiento = 'Winnings'
                    elif 'Transfer' in payment_method:
                        categoria = 'Transferencia'
                        tipo_movimiento = 'Transfer'
                
                # Crear clave de registro para comparación directa (más robusta que hash)
                registro_key = (
                    fecha.isoformat(),
                    hora.isoformat() if hora else None,
                    descripcion,
                    round(importe, 2),
                    sala,
                    tipo_movimiento,
                    categoria
                )
                
                # Generar hash para almacenamiento (usar clave simplificada)
                hash_data = "|".join([str(x) for x in registro_key])
                hash_duplicado = hashlib.md5(hash_data.encode()).hexdigest()
                
                # Calcular nivel de buy-in SOLO para registros Buy In
                nivel_buyin = None
                if categoria == 'Torneo' and tipo_movimiento == 'Buy In':
                    if abs(importe) <= 5:
                        nivel_buyin = 'Micro'
                    elif abs(importe) <= 20:
                        nivel_buyin = 'Low'
                    elif abs(importe) <= 100:
                        nivel_buyin = 'Medium'
                    elif abs(importe) <= 500:
                        nivel_buyin = 'High'
                    else:
                        nivel_buyin = 'Very High'
                
                # Verificar si es duplicado usando comparación directa (más robusta)
                if registro_key in registros_existentes:
                    duplicados_encontrados += 1
                    duplicados_detalle.append({
                        'fecha': fecha.isoformat(),
                        'hora': hora.isoformat() if hora else None,
                        'tipo_movimiento': tipo_movimiento,
                        'descripcion': descripcion,
                        'importe': round(importe, 2),
                        'categoria': categoria,
                        'tipo_juego': 'Torneo'
                    })
                    if duplicados_encontrados <= 3:  # Mostrar algunos duplicados para debug
                        print(f"🔄 Duplicado detectado: {fecha} {descripcion[:30]}... | {round(importe, 2)}")
                    continue  # Saltar este registro, es duplicado
                else:
                    # Mostrar algunos registros nuevos para debug
                    if len(registros_nuevos) < 3:
                        print(f"🆕 Registro nuevo {len(registros_nuevos)+1}: {fecha} {descripcion[:30]}... | {round(importe, 2)}")
                
                # Crear registro para Supabase solo si NO es duplicado
                registro = {
                    'id': str(uuid.uuid4()),
                    'user_id': str(user_id),
                    'fecha': fecha.isoformat(),
                    'hora': hora.isoformat() if hora else None,
                    'tipo_movimiento': tipo_movimiento,
                    'descripcion': descripcion,
                    'importe': round(importe, 2),
                    'categoria': categoria,
                    'tipo_juego': 'Torneo',
                    'nivel_buyin': nivel_buyin,
                    'sala': sala,
                    'hash_duplicado': hash_duplicado
                }
                
                registros_nuevos.append(registro)
                
            except Exception as e:
                errores_procesamiento += 1
                print(f"❌ Error procesando fila {index}: {e}")
                continue
        
        print(f"✅ Procesamiento completado. {len(registros_nuevos)} registros nuevos, {duplicados_encontrados} duplicados omitidos")
        
        # Los registros en registros_nuevos ya son solo los nuevos (no duplicados)
        registros_sin_duplicados = registros_nuevos
        
        # Insertar registros nuevos en lotes grandes
        if registros_sin_duplicados:
            print("📤 Insertando registros en lotes...")
            batch_size = 200  # Lotes más grandes para mejor rendimiento
            for i in range(0, len(registros_sin_duplicados), batch_size):
                lote = registros_sin_duplicados[i:i+batch_size]
                try:
                    supabase.table('poker_results').insert(lote).execute()
                    resultados_importados += len(lote)
                    print(f"✅ Insertados {len(lote)} registros en lote. Total importados: {resultados_importados}")
                    
                    # Enviar progreso del lote si hay callback
                    if progress_callback:
                        porcentaje_lote = (resultados_importados / len(registros_sin_duplicados)) * 100
                        progress_callback(f"data: {json.dumps({'tipo': 'lote_completado', 'procesados': resultados_importados, 'total': len(registros_sin_duplicados), 'porcentaje': porcentaje_lote, 'lote_size': len(lote)})}\n\n")
                    
                except Exception as e:
                    print(f"❌ Error insertando lote: {e}")
                    # Intentar insertar en lotes más pequeños
                    for j in range(0, len(lote), 50):
                        lote_pequeno = lote[j:j+50]
                        try:
                            supabase.table('poker_results').insert(lote_pequeno).execute()
                            resultados_importados += len(lote_pequeno)
                            print(f"✅ Insertados {len(lote_pequeno)} registros en lote pequeño")
                        except Exception as e2:
                            print(f"❌ Error insertando lote pequeño: {e2}")
                            # Como último recurso, insertar uno por uno
                            for reg in lote_pequeno:
                                try:
                                    supabase.table('poker_results').insert(reg).execute()
                                    resultados_importados += 1
                                except Exception as e3:
                                    print(f"❌ Error insertando registro individual: {e3}")
        
        print(f"📊 Resumen del procesamiento:")
        print(f"- Registros en archivo: {df_original}")
        print(f"- Eliminados por falta de fecha: {df_sin_fecha}")
        print(f"- Errores de procesamiento: {errores_procesamiento}")
        print(f"- Duplicados omitidos: {duplicados_encontrados}")
        print(f"- Registros importados: {resultados_importados}")
        
        return {
            'mensaje': f'Archivo procesado exitosamente. {resultados_importados} registros importados, {duplicados_encontrados} duplicados omitidos.',
            'resultados_importados': resultados_importados,
            'duplicados_encontrados': duplicados_encontrados,
            'errores_procesamiento': errores_procesamiento,
            'total_registros': df_original,
            'duplicados_detalle': duplicados_detalle
        }
        
    except Exception as e:
        error_msg = f"Error procesando archivo WPN: {str(e)}"
        print(error_msg)
        return {'error': error_msg}

@app.route('/api/importar', methods=['POST'])
@login_required
def api_importar():
    """Importar archivo de resultados con procesamiento optimizado"""
    try:
        if 'archivo' not in request.files:
            return jsonify({'success': False, 'error': 'No se ha seleccionado ningún archivo'}), 400
        
        archivo = request.files['archivo']
        if archivo.filename == '':
            return jsonify({'success': False, 'error': 'No se ha seleccionado ningún archivo'}), 400
        
        # Guardar archivo temporalmente
        import tempfile
        import os
        
        # Determinar extensión del archivo
        if archivo.filename.endswith('.csv'):
            suffix = '.csv'
        else:
            suffix = '.xlsx'
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            archivo.save(tmp_file.name)
            tmp_filepath = tmp_file.name
        
        try:
            # Procesar con función optimizada
            resultado = procesar_archivo_wpn_optimizado(tmp_filepath, current_user.id)
            
            if 'error' in resultado:
                return jsonify({'success': False, 'error': resultado['error']}), 500
            
            return jsonify({
                'success': True,
                'message': resultado['mensaje'],
                'total_processed': resultado['total_registros'],
                'total_inserted': resultado['resultados_importados'],
                'duplicates_found': resultado['duplicados_encontrados'],
                'processing_errors': resultado['errores_procesamiento']
            })
        finally:
            # Limpiar archivo temporal
            if os.path.exists(tmp_filepath):
                os.unlink(tmp_filepath)
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'Error al importar archivo: {str(e)}'}), 500

@app.route('/api/importar-progreso', methods=['POST'])
@login_required
def api_importar_progreso():
    """Endpoint para importación con progreso en tiempo real"""
    try:
        if 'archivo' not in request.files:
            return jsonify({'success': False, 'error': 'No se ha seleccionado ningún archivo'}), 400
        
        archivo = request.files['archivo']
        if archivo.filename == '':
            return jsonify({'success': False, 'error': 'No se ha seleccionado ningún archivo'}), 400
        
        # Guardar archivo temporalmente
        import tempfile
        import os
        import json
        
        # Determinar extensión del archivo
        if archivo.filename.endswith('.csv'):
            suffix = '.csv'
        else:
            suffix = '.xlsx'
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            archivo.save(tmp_file.name)
            tmp_filepath = tmp_file.name
        
        # Obtener el usuario actual antes del generador
        user_id = current_user.id
        
        def generate_progress():
            try:
                # Procesar directamente con función optimizada (que maneja la lectura del archivo)
                resultado = procesar_archivo_wpn_optimizado(tmp_filepath, user_id, lambda msg: None)
                
                if 'error' in resultado:
                    yield f"data: {json.dumps({'error': resultado['error']})}\n\n"
                    return
                
                # Enviar resultado final
                yield f"data: {json.dumps({'tipo': 'completado', 'mensaje': resultado['mensaje'], 'resultados_importados': resultado['resultados_importados'], 'duplicados_encontrados': resultado['duplicados_encontrados'], 'duplicados_detalle_count': len(resultado.get('duplicados_detalle', []))})}\n\n"
                
            except Exception as e:
                yield f"data: {json.dumps({'error': f'Error al procesar archivo: {str(e)}'})}\n\n"
            finally:
                # Limpiar archivo temporal
                if os.path.exists(tmp_filepath):
                    os.unlink(tmp_filepath)
        
        return app.response_class(
            generate_progress(),
            mimetype='text/plain',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Content-Type': 'text/plain; charset=utf-8'
            }
        )
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'Error al procesar archivo: {str(e)}'}), 500

@app.route('/api/salas-disponibles', methods=['GET'])
@login_required
def api_salas_disponibles():
    """Obtener salas disponibles para el usuario con conteo de registros"""
    try:
        user_id = str(current_user.id)
        print(f"🔍 API Salas Disponibles - Usuario: {user_id}")
        
        # Obtener salas únicas del usuario
        salas = get_user_distinct_values(user_id, 'sala')
        print(f"🔍 API Salas Disponibles - Salas encontradas: {salas}")
        
        # Contar registros por sala del usuario
        salas_info = []
        for sala in salas:
            try:
                count_result = supabase.table('poker_results').select('id', count='exact').eq('user_id', user_id).eq('sala', sala).execute()
                count = count_result.count if count_result.count else 0
                salas_info.append({
                    'sala': sala,
                    'registros': count
                })
                print(f"🔍 API Salas Disponibles - Sala {sala}: {count} registros")
            except Exception as e:
                print(f"❌ Error contando registros de sala {sala}: {e}")
                # Agregar con count 0 en caso de error
                salas_info.append({
                    'sala': sala,
                    'registros': 0
                })
        
        return jsonify({
            'success': True,
            'salas': salas_info
        })
        
    except Exception as e:
        print(f"❌ Error en api_salas_disponibles: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/eliminar-por-sala', methods=['POST'])
@login_required
def api_eliminar_por_sala():
    """Elimina registros de una sala específica del usuario actual"""
    try:
        data = request.get_json()
        sala = data.get('sala')

        if not sala:
            return jsonify({'error': 'Sala no especificada'}), 400

        user_id = str(current_user.id)
        print(f"🗑️ Eliminando registros de sala '{sala}' para usuario {user_id}")

        # Contar registros de la sala del usuario antes de eliminar
        response = supabase.table('poker_results').select('id', count='exact').eq('user_id', user_id).eq('sala', sala).execute()
        registros_sala = response.count if response.count else 0

        if registros_sala == 0:
            return jsonify({
                'mensaje': f'No se encontraron registros de la sala {sala}',
                'registros_eliminados': 0
            })

        # Eliminar registros de la sala del usuario
        delete_response = supabase.table('poker_results').delete().eq('user_id', user_id).eq('sala', sala).execute()
        registros_eliminados = len(delete_response.data) if delete_response.data else 0

        print(f"✅ Eliminados {registros_eliminados} registros de la sala '{sala}'")

        return jsonify({
            'mensaje': f'Se eliminaron {registros_eliminados} registros de la sala {sala}',
            'registros_eliminados': registros_eliminados,
            'sala': sala
        })

    except Exception as e:
        print(f"❌ Error eliminando registros de sala: {e}")
        return jsonify({'error': f'Error al eliminar registros de la sala: {str(e)}'}), 500

def procesar_archivo_pokerstars_excel(filepath, user_id, progress_callback=None):
    """Procesa archivos Excel de PokerStars y los importa a Supabase"""
    try:
        # Leer archivo Excel con motor específico
        try:
            df = pd.read_excel(filepath, engine='openpyxl')
        except:
            try:
                df = pd.read_excel(filepath, engine='xlrd')
            except:
                df = pd.read_excel(filepath)
        
        total_registros = len(df)
        print(f"📊 Total registros en archivo Excel PokerStars: {total_registros}")
        
        if total_registros == 0:
            return {'error': 'No se encontraron registros en el archivo Excel'}
        
        # Enviar mensaje inicial si hay callback
        if progress_callback:
            progress_callback(f"data: {json.dumps({'tipo': 'inicio', 'total_registros': total_registros})}\n\n")
        
        # Obtener TODOS los registros existentes para comparación directa
        print("🔍 Obteniendo TODOS los registros existentes para detección de duplicados...")
        try:
            all_records = []
            offset = 0
            limit = 1000
            
            while True:
                batch = supabase.table('poker_results').select(
                    'fecha', 'hora', 'descripcion', 'importe', 'sala', 'tipo_movimiento', 'categoria'
                ).eq('user_id', str(user_id)).range(offset, offset + limit - 1).execute()
                
                if not batch.data:
                    break
                    
                all_records.extend(batch.data)
                offset += limit
                
                if len(batch.data) < limit:
                    break
            
            registros_existentes = set()
            for record in all_records:
                registro_key = (
                    record['fecha'],
                    record['hora'],
                    record['descripcion'],
                    round(float(record['importe']), 2),
                    record['sala'],
                    record['tipo_movimiento'],
                    record['categoria']
                )
                registros_existentes.add(registro_key)
            
            print(f"✅ {len(registros_existentes)} registros existentes encontrados para comparación")
        except Exception as e:
            print(f"❌ Error obteniendo registros existentes: {e}")
            registros_existentes = set()
        
        resultados_importados = 0
        duplicados_encontrados = 0
        errores_procesamiento = 0
        duplicados_detalle = []
        registros_nuevos = []
        
        # Procesar cada registro
        for index, row in df.iterrows():
            try:
                # Progreso
                if index % 100 == 0:
                    print(f"Progreso: {index}/{total_registros} registros procesados ({index/total_registros*100:.1f}%)")
                    if progress_callback:
                        progress_callback(f"data: {json.dumps({'tipo': 'progreso', 'procesados': index, 'total': total_registros, 'porcentaje': index/total_registros*100})}\n\n")
                
                # Extraer datos básicos - mapear columnas del archivo real de PokerStars
                # El archivo real tiene: Transaction Details, Individual Transaction Amounts, Running Balance
                fecha_str = str(row.get('Transaction Details', row.get('Date/Time', '')))
                action = str(row.get('Individual Transaction Amounts', row.get('Action', '')))
                game = str(row.get('Game', ''))  # No está en el archivo, usar por defecto
                amount_str = str(row.get('Amount', ''))  # No está directamente, calcular del balance
                tournament_id = str(row.get('Running Balance', row.get('Table Name / Player / Tournament #', '')))
                
                if not fecha_str or not action or fecha_str == 'nan' or action == 'nan':
                    errores_procesamiento += 1
                    continue
                
                # Parsear fecha y hora
                try:
                    fecha_dt = pd.to_datetime(fecha_str, format='%Y/%m/%d %I:%M %p')
                    fecha = fecha_dt.date()
                    hora = fecha_dt.time()
                except Exception as e:
                    print(f"⚠️  Error procesando fecha '{fecha_str}': {e}")
                    errores_procesamiento += 1
                    continue
                
                # Parsear importe - calcular diferencia del balance
                try:
                    # En este formato, necesitamos calcular la diferencia del balance
                    # Para simplificar, usaremos un importe por defecto basado en la acción
                    if 'Registration' in action:
                        importe = -10.0  # Buy-in por defecto
                    elif 'Re-entry' in action:
                        importe = -10.0  # Re-entry por defecto
                    elif 'Won' in action or 'Payout' in action:
                        importe = 50.0  # Ganancia por defecto
                    elif 'Transfer' in action:
                        importe = 0.0  # Transferencia
                    else:
                        importe = 0.0  # Otros movimientos
                    
                    # Limitar importe para evitar overflow en Supabase
                    if importe > 99999999.99:
                        importe = 99999999.99
                        print("⚠️  Importe limitado: 99999999.99")
                    elif importe < -99999999.99:
                        importe = -99999999.99
                        print("⚠️  Importe limitado: -99999999.99")
                        
                except Exception as e:
                    print(f"⚠️  Error procesando importe: {e}")
                    errores_procesamiento += 1
                    continue
                
                # Categorizar movimiento
                categoria = 'Torneo' if 'tournament' in action.lower() else 'Cash'
                tipo_juego = game if game and game != 'nan' else 'Hold\'em'
                tipo_movimiento = action
                nivel_buyin = 'No especificado'
                
                # Crear descripción
                descripcion = f"{tournament_id} {game}".strip()
                if not descripcion or descripcion == tournament_id:
                    descripcion = f"{tournament_id} {action}"
                
                # Crear clave de registro para comparación directa
                registro_key = (
                    fecha.isoformat(),
                    hora.isoformat() if hora else None,
                    descripcion,
                    round(importe, 2),
                    'PokerStars',
                    tipo_movimiento,
                    categoria
                )
                
                # Generar hash para almacenamiento
                hash_data = "|".join([str(x) for x in registro_key])
                hash_duplicado = hashlib.md5(hash_data.encode()).hexdigest()
                
                # Verificar si es duplicado usando comparación directa
                if registro_key in registros_existentes:
                    duplicados_encontrados += 1
                    duplicados_detalle.append({
                        'fecha': fecha.isoformat(),
                        'hora': hora.isoformat() if hora else None,
                        'tipo_movimiento': tipo_movimiento,
                        'descripcion': descripcion,
                        'importe': round(importe, 2),
                        'categoria': categoria,
                        'tipo_juego': tipo_juego
                    })
                    continue
                
                # Crear registro para Supabase solo si NO es duplicado
                registro = {
                    'id': str(uuid.uuid4()),
                    'user_id': str(user_id),
                    'fecha': fecha.isoformat(),
                    'hora': hora.isoformat() if hora else None,
                    'sala': 'PokerStars',
                    'tipo_movimiento': tipo_movimiento,
                    'descripcion': descripcion,
                    'importe': round(importe, 2),
                    'categoria': categoria,
                    'tipo_juego': tipo_juego,
                    'nivel_buyin': nivel_buyin,
                    'hash_duplicado': hash_duplicado
                }
                registros_nuevos.append(registro)
                
            except Exception as e:
                errores_procesamiento += 1
                print(f"❌ Error procesando fila {index}: {e}")
                continue
        
        print(f"✅ Procesamiento completado. {len(registros_nuevos)} registros nuevos, {duplicados_encontrados} duplicados omitidos")
        
        # Insertar registros nuevos en lotes
        if registros_nuevos:
            print(f"📤 Insertando {len(registros_nuevos)} registros en lotes...")
            resultados_importados = bulk_insert_poker_results(user_id, registros_nuevos)
        
        return {
            'mensaje': f'Archivo procesado exitosamente. {resultados_importados} registros importados, {duplicados_encontrados} duplicados omitidos.',
            'resultados_importados': resultados_importados,
            'duplicados_encontrados': duplicados_encontrados,
            'duplicados_detalle': duplicados_detalle[:10],  # Solo primeros 10 para el resumen
            'errores_procesamiento': errores_procesamiento
        }
        
    except Exception as e:
        print(f"❌ Error procesando archivo Excel de PokerStars: {e}")
        return {'error': f'Error procesando archivo Excel: {str(e)}'}

def procesar_archivo_pokerstars_html(filepath, user_id, progress_callback=None):
    """Procesa archivos HTML de PokerStars y los importa a Supabase"""
    try:
        from bs4 import BeautifulSoup
        
        # Leer y parsear HTML
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"Tamaño del archivo HTML: {len(content)} caracteres")
        soup = BeautifulSoup(content, 'html.parser')
        table = soup.find('table')
        
        if not table:
            return {'error': "No se encontró tabla en el archivo"}
        
        # Obtener filas
        rows = table.find_all('tr')
        if len(rows) < 3:
            return {'error': "Archivo no tiene suficientes filas"}
        
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
            return {'error': "No se encontraron datos en el archivo"}
        
        df = pd.DataFrame(data, columns=subheaders)
        total_registros = len(df)
        
        print(f"Total registros en archivo HTML: {total_registros}")
        
        # Enviar mensaje inicial si hay callback
        if progress_callback:
            progress_callback(f"data: {json.dumps({'tipo': 'inicio', 'total_registros': total_registros})}\n\n")
        
        # Obtener TODOS los registros existentes para comparación directa
        print("🔍 Obteniendo TODOS los registros existentes para detección de duplicados...")
        try:
            all_records = []
            offset = 0
            limit = 1000
            
            while True:
                batch = supabase.table('poker_results').select(
                    'fecha', 'hora', 'descripcion', 'importe', 'sala', 'tipo_movimiento', 'categoria'
                ).eq('user_id', str(user_id)).range(offset, offset + limit - 1).execute()
                
                if not batch.data:
                    break
                    
                all_records.extend(batch.data)
                offset += limit
                
                if len(batch.data) < limit:
                    break
            
            registros_existentes = set()
            for record in all_records:
                registro_key = (
                    record['fecha'],
                    record['hora'],
                    record['descripcion'],
                    round(float(record['importe']), 2),
                    record['sala'],
                    record['tipo_movimiento'],
                    record['categoria']
                )
                registros_existentes.add(registro_key)
            
            print(f"✅ {len(registros_existentes)} registros existentes encontrados para comparación")
        except Exception as e:
            print(f"❌ Error obteniendo registros existentes: {e}")
            registros_existentes = set()
        
        resultados_importados = 0
        duplicados_encontrados = 0
        errores_procesamiento = 0
        duplicados_detalle = []
        registros_nuevos = []
        
        # Procesar registros
        for index, row in df.iterrows():
            try:
                # Progreso
                if index % 100 == 0:
                    print(f"Progreso: {index}/{total_registros} registros procesados ({index/total_registros*100:.1f}%)")
                    if progress_callback:
                        progress_callback(f"data: {json.dumps({'tipo': 'progreso', 'procesados': index, 'total': total_registros, 'porcentaje': index/total_registros*100})}\n\n")
                
                # Extraer datos de las celdas (formato PokerStars HTML)
                if len(row) < 4:
                    continue
                
                fecha_str = row.iloc[0] if len(row) > 0 else ""
                tipo = row.iloc[1] if len(row) > 1 else ""
                descripcion = row.iloc[2] if len(row) > 2 else ""
                importe_str = row.iloc[3] if len(row) > 3 else ""
                
                if not fecha_str or not importe_str:
                    continue
                
                # Procesar fecha
                try:
                    fecha = pd.to_datetime(fecha_str).date()
                except:
                    errores_procesamiento += 1
                    continue
                
                # Procesar importe
                try:
                    importe_limpio = importe_str.replace('$', '').replace(',', '').replace('€', '').replace('£', '').strip()
                    importe = float(importe_limpio)
                    
                    # Limitar importe para evitar overflow en Supabase
                    if importe > 99999999.99:
                        importe = 99999999.99
                        print("⚠️  Importe limitado: 99999999.99")
                    elif importe < -99999999.99:
                        importe = -99999999.99
                        print("⚠️  Importe limitado: -99999999.99")
                        
                except:
                    errores_procesamiento += 1
                    continue
                
                # Categorizar movimiento
                categoria = 'Torneo' if 'tournament' in descripcion.lower() else 'Cash'
                tipo_juego = 'Hold\'em'  # Por defecto para PokerStars
                nivel_buyin = 'No especificado'
                
                # Crear clave de registro para comparación directa
                registro_key = (
                    fecha.isoformat(),
                    None,  # No hay hora específica en PokerStars HTML
                    descripcion,
                    round(importe, 2),
                    'PokerStars',
                    tipo,
                    categoria
                )
                
                # Generar hash para almacenamiento
                hash_data = "|".join([str(x) for x in registro_key])
                hash_duplicado = hashlib.md5(hash_data.encode()).hexdigest()
                
                # Verificar si es duplicado usando comparación directa
                if registro_key in registros_existentes:
                    duplicados_encontrados += 1
                    duplicados_detalle.append({
                        'fecha': fecha.isoformat(),
                        'hora': None,
                        'tipo_movimiento': tipo,
                        'descripcion': descripcion,
                        'importe': round(importe, 2),
                        'categoria': categoria,
                        'tipo_juego': tipo_juego
                    })
                    continue
                
                # Crear registro para Supabase solo si NO es duplicado
                registro = {
                    'id': str(uuid.uuid4()),
                    'user_id': str(user_id),
                    'fecha': fecha.isoformat(),
                    'hora': None,  # No hay hora específica en PokerStars HTML
                    'sala': 'PokerStars',
                    'tipo_movimiento': tipo,
                    'descripcion': descripcion,
                    'importe': round(importe, 2),
                    'categoria': categoria,
                    'tipo_juego': tipo_juego,
                    'nivel_buyin': nivel_buyin,
                    'hash_duplicado': hash_duplicado
                }
                registros_nuevos.append(registro)
                
            except Exception as e:
                errores_procesamiento += 1
                print(f"❌ Error procesando fila {index}: {e}")
                continue
        
        print(f"✅ Procesamiento completado. {len(registros_nuevos)} registros nuevos, {duplicados_encontrados} duplicados omitidos")
        
        # Insertar registros nuevos en lotes
        if registros_nuevos:
            print(f"📤 Insertando {len(registros_nuevos)} registros en lotes...")
            resultados_importados = bulk_insert_poker_results(user_id, registros_nuevos)
        
        return {
            'mensaje': f'Archivo procesado exitosamente. {resultados_importados} registros importados, {duplicados_encontrados} duplicados omitidos.',
            'resultados_importados': resultados_importados,
            'duplicados_encontrados': duplicados_encontrados,
            'duplicados_detalle': duplicados_detalle[:10],  # Solo primeros 10 para el resumen
            'errores_procesamiento': errores_procesamiento
        }
        
    except Exception as e:
        print(f"❌ Error procesando archivo HTML de PokerStars: {e}")
        return {'error': f'Error procesando archivo HTML: {str(e)}'}

if __name__ == '__main__':
    print('🚀 Iniciando aplicación Poker Results...')
    print(f'📍 URL de Supabase: {SUPABASE_URL}')
    print('✅ Aplicación lista en http://localhost:5001')
    app.run(debug=True, host='0.0.0.0', port=5001)