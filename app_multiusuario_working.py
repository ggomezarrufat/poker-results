#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
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
        
        # Leer el archivo
        if archivo.filename.endswith('.xlsx'):
            df = pd.read_excel(archivo)
        elif archivo.filename.endswith('.csv'):
            df = pd.read_csv(archivo)
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
    """Procesa archivos Excel/CSV de WPN con inserción masiva optimizada para Supabase"""
    try:
        # Leer el archivo (Excel o CSV)
        if filepath.endswith('.csv'):
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath)
        print(f"Total registros en archivo: {len(df)}")
        
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
        
        # Procesar todos los registros primero
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
                    except:
                        # Si no se puede parsear la fecha, usar fecha actual
                        fecha = datetime.now().date()
                        hora = datetime.now().time()
                    
                    # Extraer importe del texto con límite seguro
                    importe = 0.0
                    try:
                        if 'Tournament Registration' in descripcion:
                            # Extraer importe del balance (simplificado)
                            importe = -float(importe_str) if importe_str.replace('.', '').replace('-', '').isdigit() else 0
                        elif 'Tournament Won' in descripcion or 'Tournament Interim Payout' in descripcion:
                            importe = float(importe_str) if importe_str.replace('.', '').replace('-', '').isdigit() else 0
                        
                        # Limitar importe a rango seguro para Supabase (precision 10, scale 2 = max 99,999,999.99)
                        if abs(importe) > 99999999.99:
                            importe = 99999999.99 if importe > 0 else -99999999.99
                            print(f"⚠️  Importe limitado: {importe}")
                    except (ValueError, TypeError):
                        importe = 0.0
                    
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
                
                # Generar hash para detectar duplicados
                hash_data = f"{fecha.isoformat()}{hora.isoformat()}{descripcion}{importe}{sala}"
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
                
                # Crear registro para Supabase
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
        
        print(f"✅ Procesamiento completado. {len(registros_nuevos)} registros preparados")
        
        # Verificar duplicados en lote
        print("🔍 Verificando duplicados...")
        hashes_existentes = set()
        if registros_nuevos:
            # Obtener todos los hashes existentes de una vez
            try:
                existing_hashes = supabase.table('poker_results').select('hash_duplicado').eq('user_id', str(user_id)).execute()
                hashes_existentes = set([record['hash_duplicado'] for record in existing_hashes.data])
                print(f"✅ {len(hashes_existentes)} hashes existentes encontrados")
            except Exception as e:
                print(f"❌ Error obteniendo hashes existentes: {e}")
        
        # Filtrar duplicados
        registros_sin_duplicados = []
        for registro in registros_nuevos:
            if registro['hash_duplicado'] in hashes_existentes:
                duplicados_encontrados += 1
                duplicados_detalle.append({
                    'fecha': registro['fecha'],
                    'hora': registro['hora'],
                    'tipo_movimiento': registro['tipo_movimiento'],
                    'descripcion': registro['descripcion'],
                    'importe': registro['importe'],
                    'categoria': registro['categoria'],
                    'tipo_juego': registro['tipo_juego']
                })
            else:
                registros_sin_duplicados.append(registro)
        
        print(f"✅ {duplicados_encontrados} duplicados encontrados, {len(registros_sin_duplicados)} registros nuevos")
        
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
                # Leer el archivo para obtener el total de registros
                if tmp_filepath.endswith('.csv'):
                    df = pd.read_csv(tmp_filepath)
                else:
                    df = pd.read_excel(tmp_filepath)
                
                total_registros = len(df)
                
                # Enviar mensaje de inicio
                yield f"data: {json.dumps({'tipo': 'inicio', 'total_registros': total_registros})}\n\n"
                
                # Simular progreso de procesamiento
                for i in range(0, total_registros + 1, 50):
                    if i > total_registros:
                        i = total_registros
                    
                    porcentaje = (i / total_registros) * 100
                    yield f"data: {json.dumps({'tipo': 'progreso', 'procesados': i, 'total': total_registros, 'porcentaje': porcentaje})}\n\n"
                    
                    # Simular tiempo de procesamiento
                    import time
                    time.sleep(0.1)
                
                # Procesar con función optimizada (sin callback)
                resultado = procesar_archivo_wpn_optimizado(tmp_filepath, user_id)
                
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
    """Obtener salas disponibles para el usuario"""
    try:
        salas = get_user_distinct_values(current_user.id, 'sala')
        
        return jsonify({
            'success': True,
            'salas': salas
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    print('🚀 Iniciando aplicación Poker Results...')
    print(f'📍 URL de Supabase: {SUPABASE_URL}')
    print('✅ Aplicación lista en http://localhost:5001')
    app.run(debug=True, host='0.0.0.0', port=5001)