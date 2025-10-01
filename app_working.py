#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import uuid
import json
import pandas as pd
import hashlib
import time
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, Response, send_from_directory
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, validators
from supabase import create_client, Client
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import httpx

# Importar Flask-RESTX para Swagger
from flask_restx import Api, Resource, fields, Namespace

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')

# Configurar Swagger/OpenAPI
app.config['RESTX_MASK_SWAGGER'] = False
api = Api(
    app,
    version='1.0',
    title='Poker Results API',
    description='API para análisis de resultados de poker con soporte multiusuario',
    doc='/swagger/',
    prefix='/api'
)

# Crear namespaces para organizar los endpoints
auth_ns = Namespace('auth', description='Autenticación de usuarios')
reports_ns = Namespace('reports', description='Informes y reportes')
analysis_ns = Namespace('analysis', description='Análisis avanzado')
import_ns = Namespace('import', description='Importación de datos')
admin_ns = Namespace('admin', description='Administración')

# Registrar namespaces
api.add_namespace(auth_ns)
api.add_namespace(reports_ns)
api.add_namespace(analysis_ns)
api.add_namespace(import_ns)
api.add_namespace(admin_ns)

# =============================================================================
# MODELOS DE SWAGGER
# =============================================================================

# Modelos de respuesta
error_model = api.model('Error', {
    'error': fields.String(required=True, description='Mensaje de error')
})

success_model = api.model('Success', {
    'mensaje': fields.String(required=True, description='Mensaje de éxito')
})

# Modelo de usuario
user_model = api.model('User', {
    'id': fields.String(description='ID del usuario'),
    'username': fields.String(description='Nombre de usuario'),
    'email': fields.String(description='Email del usuario'),
    'is_admin': fields.Boolean(description='Es administrador')
})

# Modelo de login
login_model = api.model('LoginRequest', {
    'username': fields.String(required=True, description='Nombre de usuario'),
    'password': fields.String(required=True, description='Contraseña')
})

login_response_model = api.model('LoginResponse', {
    'mensaje': fields.String(description='Mensaje de respuesta'),
    'token': fields.String(description='Token de autenticación'),
    'user_id': fields.String(description='ID del usuario'),
    'username': fields.String(description='Nombre de usuario')
})

# Modelo de resultado de poker
poker_result_model = api.model('PokerResult', {
    'id': fields.String(description='ID del resultado'),
    'fecha': fields.String(description='Fecha del movimiento'),
    'hora': fields.String(description='Hora del movimiento'),
    'tipo_movimiento': fields.String(description='Tipo de movimiento'),
    'descripcion': fields.String(description='Descripción'),
    'importe': fields.Float(description='Importe'),
    'categoria': fields.String(description='Categoría'),
    'tipo_juego': fields.String(description='Tipo de juego'),
    'nivel_buyin': fields.String(description='Nivel de buy-in'),
    'sala': fields.String(description='Sala')
})

# Modelo de estadísticas
stats_model = api.model('Stats', {
    'total_registros': fields.Integer(description='Total de registros'),
    'total_torneos': fields.Integer(description='Total de torneos'),
    'suma_importes': fields.Float(description='Suma de importes'),
    'resultado_economico': fields.Float(description='Resultado económico')
})

# Modelo de opciones
opciones_model = api.model('Opciones', {
    'categorias': fields.List(fields.String, description='Categorías disponibles'),
    'tipos_juego': fields.List(fields.String, description='Tipos de juego disponibles'),
    'niveles_buyin': fields.List(fields.String, description='Niveles de buy-in disponibles'),
    'salas': fields.List(fields.String, description='Salas disponibles')
})

# Configurar Supabase
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL y SUPABASE_KEY deben estar configurados en el archivo .env")

# Configurar cliente de Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Función de reintentos para consultas de Supabase
def ejecutar_con_reintentos(func, max_intentos=3, delay=1):
    """Ejecuta una función con reintentos en caso de error de conexión"""
    for intento in range(max_intentos):
        try:
            return func()
        except (httpx.ReadError, httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError) as e:
            print(f"⚠️  Intento {intento + 1} falló: {type(e).__name__}: {e}")
            if intento < max_intentos - 1:
                print(f"🔄 Reintentando en {delay} segundos...")
                time.sleep(delay)
                delay *= 2  # Backoff exponencial
            else:
                print(f"❌ Todos los intentos fallaron después de {max_intentos} intentos")
                raise e
        except Exception as e:
            # Para otros errores, no reintentar
            print(f"❌ Error no recuperable: {type(e).__name__}: {e}")
            raise e

def obtener_registros_completos_supabase(table_name, select_fields, filter_user_id, max_records=20000):
    """
    Obtiene todos los registros de una tabla superando el límite de 1000 de Supabase
    usando consultas por lotes.
    """
    try:
        all_records = []
        offset = 0
        batch_size = 1000
        
        print(f"🔍 Obteniendo registros de {table_name} para usuario {filter_user_id}")
        
        while True:
            # Consulta por lote con reintentos
            def get_batch():
                return supabase.table(table_name).select(select_fields).eq('user_id', filter_user_id).range(offset, offset + batch_size - 1).execute()
            
            batch_result = ejecutar_con_reintentos(get_batch)
            
            if not batch_result.data:
                break
                
            all_records.extend(batch_result.data)
            
            print(f"📊 Lote {offset//batch_size + 1}: {len(batch_result.data)} registros (total: {len(all_records)})")
            
            # Si obtenemos menos registros que el tamaño del lote, hemos terminado
            if len(batch_result.data) < batch_size:
                break
                
            offset += batch_size
            
            # Límite de seguridad
            if offset >= max_records:
                print(f"⚠️  Límite de seguridad alcanzado: {max_records} registros")
                break
        
        print(f"✅ Total de registros obtenidos: {len(all_records)}")
        return all_records
        
    except Exception as e:
        print(f"❌ Error obteniendo registros completos: {e}")
        return []

def obtener_valores_unicos_optimizado(table_name, field_name, filter_user_id, max_records=20000):
    """
    Obtiene valores únicos de un campo específico, parando cuando encuentra todos los valores únicos.
    Optimizado para filtros de interfaz que solo necesitan las opciones disponibles.
    """
    try:
        valores_unicos = set()
        offset = 0
        batch_size = 1000
        sin_cambios_consecutivos = 0
        
        print(f"🔍 Obteniendo valores únicos de {field_name} en {table_name}")
        
        # Para salas y categorías, NO usar optimización debido a distribución irregular de registros
        usar_optimizacion = field_name not in ['sala', 'categoria']
        
        while True:
            # Consulta por lote
            def get_batch():
                return supabase.table(table_name).select(field_name).eq('user_id', filter_user_id).range(offset, offset + batch_size - 1).execute()
            
            batch_result = ejecutar_con_reintentos(get_batch)
            
            if not batch_result.data:
                break
            
            # Contar valores únicos antes
            valores_antes = len(valores_unicos)
            
            # Agregar nuevos valores únicos
            for record in batch_result.data:
                if record.get(field_name):
                    valores_unicos.add(record[field_name])
            
            valores_despues = len(valores_unicos)
            nuevos_valores = valores_despues - valores_antes
            
            print(f"📊 Lote {offset//batch_size + 1}: {len(batch_result.data)} registros, +{nuevos_valores} valores únicos (total: {len(valores_unicos)})")
            
            # Solo aplicar optimización si no es el campo 'sala'
            if usar_optimizacion:
                # Si no encontramos nuevos valores únicos en 2 lotes consecutivos, probablemente ya tenemos todos
                if nuevos_valores == 0:
                    sin_cambios_consecutivos += 1
                    if sin_cambios_consecutivos >= 2:
                        print(f"✅ Optimización: No se encontraron nuevos valores únicos en {sin_cambios_consecutivos} lotes, terminando")
                        break
                else:
                    sin_cambios_consecutivos = 0
            
            # Si obtenemos menos registros que el tamaño del lote, hemos terminado
            if len(batch_result.data) < batch_size:
                break
                
            offset += batch_size
            
            # Límite de seguridad
            if offset >= max_records:
                print(f"⚠️  Límite de seguridad alcanzado: {max_records} registros")
                break
        
        valores_lista = list(valores_unicos)
        print(f"✅ Valores únicos obtenidos: {len(valores_lista)} - {valores_lista}")
        return valores_lista
        
    except Exception as e:
        print(f"❌ Error obteniendo valores únicos: {e}")
        return []

# Configurar Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor, inicia sesión para acceder a esta página.'

# Clase User para Flask-Login
class User(UserMixin):
    def __init__(self, id, username, email, is_admin=False, is_active=True):
        self.id = str(id)  # Asegurar que sea string
        self.username = username
        self.email = email
        self._is_admin = is_admin
        self._is_active = is_active
    
    @property
    def is_admin(self):
        return self._is_admin
    
    @property
    def is_active(self):
        return self._is_active
    
    @is_active.setter
    def is_active(self, value):
        self._is_active = value

@login_manager.user_loader
def load_user(user_id):
    try:
        # Buscar usuario en Supabase usando la API REST directamente
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
        print(f"Error cargando usuario: {e}")
    return None

# Formularios
class LoginForm(FlaskForm):
    username = StringField('Usuario', [validators.Length(min=4, max=25)])
    password = PasswordField('Contraseña', [validators.DataRequired()])
    remember_me = BooleanField('Recordarme')
    submit = SubmitField('Iniciar Sesión')

class UserForm(FlaskForm):
    username = StringField('Usuario', [validators.Length(min=4, max=25)])
    email = StringField('Email', [validators.Email()])
    password = PasswordField('Contraseña', [validators.Length(min=6)])
    password_confirm = PasswordField('Confirmar Contraseña', [validators.EqualTo('password', message='Las contraseñas deben coincidir')])
    is_admin = BooleanField('Es Administrador')
    is_active = BooleanField('Activo')
    submit = SubmitField('Registrarse')

# Rutas
@app.route('/')
@login_required
def index():
    """Página principal"""
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Página de login"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        try:
            # Buscar usuario en Supabase usando la API REST directamente
            response = supabase.table('users').select('*').eq('username', form.username.data).execute()
            
            if response.data:
                user_data = response.data[0]
                # Verificar contraseña con método scrypt
                if check_password_hash(user_data['password_hash'], form.password.data):
                    user = User(
                        id=user_data['id'],
                        username=user_data['username'],
                        email=user_data['email'],
                        is_admin=user_data.get('is_admin', False),
                        is_active=user_data.get('is_active', True)
                    )
                    login_user(user, remember=form.remember_me.data)
                    
                    # Actualizar último login
                    supabase.table('users').update({'last_login': datetime.now().isoformat()}).eq('id', user_data['id']).execute()
                    
                    flash('¡Bienvenido!', 'success')
                    return redirect(url_for('index'))
                else:
                    flash('Usuario o contraseña incorrectos', 'error')
            else:
                flash('Usuario o contraseña incorrectos', 'error')
        except Exception as e:
            flash('Error al iniciar sesión. Intenta de nuevo.', 'error')
            print(f"Error en login: {e}")
    
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Página de registro de usuarios"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = UserForm()
    # Remover campos de admin para registro público
    form.is_admin.data = False
    form.is_active.data = True
    
    if form.validate_on_submit():
        try:
            # Verificar si el usuario ya existe
            existing_user = supabase.table('users').select('username').eq('username', form.username.data).execute()
            if existing_user.data:
                flash('El nombre de usuario ya existe. Por favor, elige otro.', 'error')
                return render_template('register.html', form=form)
            
            existing_email = supabase.table('users').select('email').eq('email', form.email.data).execute()
            if existing_email.data:
                flash('El email ya está registrado. Por favor, usa otro email.', 'error')
                return render_template('register.html', form=form)
            
            # Crear nuevo usuario
            user_id = str(uuid.uuid4())
            password_hash = generate_password_hash(form.password.data, method='scrypt')
            
            user_data = {
                'id': user_id,
                'username': form.username.data,
                'email': form.email.data,
                'password_hash': password_hash,
                'is_admin': False,
                'is_active': True,
                'created_at': datetime.now().isoformat()
            }
            
            try:
                supabase.table('users').insert(user_data).execute()
            except Exception as insert_error:
                if "row-level security policy" in str(insert_error):
                    flash('Error: Las políticas de seguridad están bloqueando el registro. Contacta al administrador.', 'error')
                    print(f"Error RLS en registro: {insert_error}")
                    return render_template('register.html', form=form)
                else:
                    raise insert_error
            
            flash('¡Usuario registrado exitosamente! Ya puedes iniciar sesión.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            flash('Error al registrar el usuario. Por favor, intenta de nuevo.', 'error')
            print(f"Error en registro: {e}")
    
    return render_template('register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    """Cerrar sesión"""
    logout_user()
    flash('Has cerrado sesión exitosamente.', 'info')
    return redirect(url_for('login'))

@app.route('/admin')
@login_required
def admin():
    """Panel de administración"""
    if not current_user.is_admin:
        flash('No tienes permisos para acceder a esta página.', 'error')
        return redirect(url_for('index'))
    
    try:
        # Obtener todos los usuarios
        users_response = supabase.table('users').select('*').execute()
        users = users_response.data if users_response.data else []
        
        # Obtener estadísticas
        stats_response = supabase.table('poker_results').select('*').execute()
        total_records = len(stats_response.data) if stats_response.data else 0
        
        return render_template('admin.html', users=users, total_records=total_records)
    except Exception as e:
        flash('Error al cargar datos de administración.', 'error')
        print(f"Error en admin: {e}")
        return render_template('admin.html', users=[], total_records=0)

@app.route('/importar')
@login_required
def importar():
    """Página de importación de datos"""
    return render_template('importar.html')

@app.route('/analisis')
def analisis():
    """Página de análisis"""
    try:
        # Usar usuario admin por defecto si no hay sesión
        if current_user.is_authenticated:
            user_id = str(current_user.id)
            print(f"🔍 Usuario autenticado para análisis: {user_id}")
        else:
            user_id = "00000000-0000-0000-0000-000000000001"  # Usuario admin por defecto
            print(f"🔍 Usando usuario por defecto para análisis: {user_id}")
        
        # Obtener datos del usuario
        user_data = supabase.table('poker_results').select('*').eq('user_id', user_id).execute()
        records = user_data.data if user_data.data else []
        
        return render_template('analisis.html', records=records)
    except Exception as e:
        flash('Error al cargar datos de análisis.', 'error')
        print(f"Error en análisis: {e}")
        return render_template('analisis.html', records=[])

@app.route('/informes')
def informes():
    """Página de informes"""
    try:
        # Usar usuario admin por defecto si no hay sesión
        if current_user.is_authenticated:
            user_id = str(current_user.id)
            print(f"🔍 Usuario autenticado para informes: {user_id}")
        else:
            user_id = "00000000-0000-0000-0000-000000000001"  # Usuario admin por defecto
            print(f"🔍 Usando usuario por defecto para informes: {user_id}")
        
        # Obtener datos del usuario
        user_data = supabase.table('poker_results').select('*').eq('user_id', user_id).execute()
        records = user_data.data if user_data.data else []
        
        return render_template('informes.html', records=records)
    except Exception as e:
        flash('Error al cargar datos de informes.', 'error')
        print(f"Error en informes: {e}")
        return render_template('informes.html', records=[])

# Funciones auxiliares para procesamiento de archivos (restauradas del código original)
def generar_hash_duplicado(fecha, hora, payment_method, descripcion, money_in, money_out, sala):
    """Genera un hash único para detectar duplicados"""
    contenido = f"{fecha}_{hora}_{payment_method}_{descripcion}_{money_in}_{money_out}_{sala}"
    return hashlib.sha256(contenido.encode()).hexdigest()

def categorizar_movimiento(payment_category, payment_method, description):
    """Categoriza automáticamente los movimientos basándose en los datos de WPN - VERSIÓN SQLITE"""
    
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
        'Winnings': 'Winnings',
        'Buy In': 'Buy In',
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
    tipos_movimiento_torneo = ['Buy In', 'Winnings', 'Bounty', 'Fee', 'Reentry Fee', 'Reentry Buy In', 'Unregister Buy In', 'Unregister Fee', 'Sit & Crush Jackpot']
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
    """Clasifica el nivel de buy-in de un torneo - VERSIÓN SQLITE"""
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

def determinar_categoria_pago(payment_method):
    """Determina la categoría de pago basada en el tipo de movimiento"""
    if payment_method in ['Buy In', 'Winnings', 'Bounty', 'Fee', 'Reentry Fee', 'Reentry Buy In', 'Unregister Buy In', 'Unregister Fee', 'Sit & Crush Jackpot']:
        return 'OnDemand Tournament'
    elif payment_method in ['Money Added', 'Money Out', 'Money In']:
        return 'Cash'
    elif payment_method in ['Deposit']:
        return 'Deposit'
    elif payment_method in ['Withdrawal', 'Payout']:
        return 'Withdrawal'
    else:
        return 'Other'

def categorizar_movimiento_pokerstars(action, game, tournament_id):
    """Categorizar movimientos específicos de Pokerstars"""
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
        # Detectar tipos específicos ANTES que patrones genéricos
        if 'badugi' in game_lower:
            tipo_juego = 'PL Badugi'
        elif 'limit horse' in game_lower:
            tipo_juego = 'Limit Horse'
        elif '8-game' in game_lower or '8 game' in game_lower:
            tipo_juego = 'Limit 8-Game'
        elif 'horse' in game_lower:
            tipo_juego = 'HORSE'
        elif 'courchevel' in game_lower:
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

def reclasificar_niveles_buyin_automatica(user_id):
    """Reclasifica automáticamente los niveles de buy-in para registros de torneos - VERSIÓN MEJORADA"""
    try:
        print(f"🔄 Iniciando reclasificación de niveles de buy-in para usuario {user_id}")
        
        # Obtener todos los registros de torneos con Buy In que ya tienen nivel_buyin
        buyins_clasificados = ejecutar_con_reintentos(
            lambda: supabase.table('poker_results').select('*').eq('categoria', 'Torneo').eq('tipo_movimiento', 'Buy In').not_.is_('nivel_buyin', 'null').eq('user_id', str(user_id)).execute()
        )
        
        if not buyins_clasificados.data:
            print("⚠️  No se encontraron registros Buy In clasificados")
            return 0
        
        print(f"📊 Encontrados {len(buyins_clasificados.data)} registros Buy In clasificados")
        
        # Obtener registros de torneos sin clasificar (todos los tipos de movimiento de torneos)
        # Procesar en lotes para evitar límites de Supabase
        registros_sin_clasificar = []
        offset = 0
        batch_size = 1000
        
        while True:
            batch = ejecutar_con_reintentos(
                lambda: supabase.table('poker_results').select('*').eq('categoria', 'Torneo').in_('tipo_movimiento', ['Bounty', 'Winnings', 'Sit & Crush Jackpot', 'Fee', 'Reentry Fee', 'Reentry Buy In', 'Unregister Buy In', 'Unregister Fee', 'Tournament Rebuy', 'Ticket']).is_('nivel_buyin', 'null').eq('user_id', str(user_id)).range(offset, offset + batch_size - 1).execute()
            )
            
            if not batch.data:
                break
                
            registros_sin_clasificar.extend(batch.data)
            offset += batch_size
            
            print(f"📊 Procesando lote: {len(batch.data)} registros (total acumulado: {len(registros_sin_clasificar)})")
            
            # Si obtenemos menos registros que el tamaño del lote, hemos terminado
            if len(batch.data) < batch_size:
                break
        
        if not registros_sin_clasificar:
            print("⚠️  No se encontraron registros sin clasificar")
            return 0
        
        print(f"📊 Encontrados {len(registros_sin_clasificar)} registros sin clasificar")
        
        # Crear múltiples diccionarios para búsqueda rápida
        descripcion_exacta = {}  # Descripción exacta -> nivel_buyin
        torneo_id_nivel = {}     # ID torneo -> nivel_buyin
        patron_nivel = {}        # Patrón de descripción -> nivel_buyin
        
        for buyin in buyins_clasificados.data:
            descripcion = buyin['descripcion']
            nivel = buyin['nivel_buyin']
            
            # Método 1: Descripción exacta
            descripcion_exacta[descripcion] = nivel
            
            # Método 2: ID del torneo (primeros números)
            partes = descripcion.split(' ', 1)
            if len(partes) > 1:
                torneo_id = partes[0]
                torneo_id_nivel[torneo_id] = nivel
            
            # Método 3: Patrón simplificado (sin precio final)
            # Ejemplo: "28773439 $3 PLO Hi/Lo Turbo - On Demand $3.3" -> "28773439 $3 PLO Hi/Lo Turbo - On Demand"
            if ' $' in descripcion and descripcion.count('$') >= 2:
                # Extraer todo hasta el último $ y espacio
                ultimo_dolar = descripcion.rfind('$')
                if ultimo_dolar > 0:
                    patron = descripcion[:ultimo_dolar].strip()
                    patron_nivel[patron] = nivel
        
        reclasificados = 0
        
        for registro in registros_sin_clasificar:
            try:
                nivel_buyin = None
                descripcion = registro['descripcion']
                
                # Método 1: Búsqueda exacta por descripción
                if descripcion in descripcion_exacta:
                    nivel_buyin = descripcion_exacta[descripcion]
                    print(f"✅ Coincidencia exacta: {descripcion[:50]}... -> {nivel_buyin}")
                
                    # Método 2: Búsqueda por ID del torneo
                if not nivel_buyin:
                    partes = descripcion.split(' ', 1)
                    if len(partes) > 1:
                        torneo_id = partes[0]
                        if torneo_id in torneo_id_nivel:
                            nivel_buyin = torneo_id_nivel[torneo_id]
                            print(f"✅ Coincidencia por ID: {torneo_id} -> {nivel_buyin}")
                
                # Método 3: Búsqueda por patrón simplificado
                if not nivel_buyin:
                    if ' $' in descripcion and descripcion.count('$') >= 2:
                        ultimo_dolar = descripcion.rfind('$')
                        if ultimo_dolar > 0:
                            patron = descripcion[:ultimo_dolar].strip()
                            if patron in patron_nivel:
                                nivel_buyin = patron_nivel[patron]
                                print(f"✅ Coincidencia por patrón: {patron[:50]}... -> {nivel_buyin}")
                
                # Método 4: Si no se encuentra, clasificar por importe
                if not nivel_buyin:
                    nivel_buyin = clasificar_nivel_buyin(registro['importe'])
                    print(f"✅ Clasificado por importe: {registro['importe']} -> {nivel_buyin}")
                
                if nivel_buyin:
                    # Actualizar registro en Supabase (simple, sin reintentos complejos)
                    try:
                        supabase.table('poker_results').update({'nivel_buyin': nivel_buyin}).eq('id', registro['id']).execute()
                        reclasificados += 1
                    except Exception as e:
                        print(f"⚠️  Error actualizando registro {registro['id']}: {e}")
                        continue
                    
            except Exception as e:
                print(f"❌ Error reclasificando registro {registro['id']}: {e}")
                continue
        
        print(f"✅ Reclasificación completada: {reclasificados} registros actualizados")
        return reclasificados
        
    except Exception as e:
        print(f"❌ Error en reclasificación automática: {e}")
        return 0

def reclasificar_pokerstars_automatica(user_id):
    """Reclasifica automáticamente registros de Pokerstars buscando datos del Buy In padre"""
    try:
        print(f"🔄 Iniciando reclasificación específica de Pokerstars para usuario {user_id}")
        
        # Obtener todos los registros Buy In de Pokerstars que tienen nivel_buyin y tipo_juego clasificados
        buyins_pokerstars = ejecutar_con_reintentos(
            lambda: supabase.table('poker_results').select('*').eq('categoria', 'Torneo').eq('tipo_movimiento', 'Buy In').eq('sala', 'Pokerstars').not_.is_('nivel_buyin', 'null').neq('tipo_juego', 'Torneo').eq('user_id', str(user_id)).execute()
        )
        
        if not buyins_pokerstars.data:
            print("⚠️  No se encontraron registros Buy In de Pokerstars clasificados")
            return 0
        
        print(f"📊 Encontrados {len(buyins_pokerstars.data)} registros Buy In de Pokerstars clasificados")
        
        # Crear diccionarios de mapeo para Pokerstars
        pokerstars_mapping = {}  # tournament_id -> {nivel_buyin, tipo_juego}
        
        for buyin in buyins_pokerstars.data:
            descripcion = buyin['descripcion']
            # Extraer tournament_id de la descripción de Pokerstars
            # Formato: "tournament_id game_description"
            partes = descripcion.split(' ', 1)
            if len(partes) > 0:
                tournament_id = partes[0]
                pokerstars_mapping[tournament_id] = {
                    'nivel_buyin': buyin['nivel_buyin'],
                    'tipo_juego': buyin['tipo_juego'],
                    'descripcion_completa': descripcion
                }
        
        print(f"📊 Creado mapeo para {len(pokerstars_mapping)} torneos de Pokerstars")
        
        # Obtener registros de Pokerstars que necesitan reclasificación
        tipos_a_reclasificar = ['Bounty', 'Winnings', 'Reentry Buy In', 'Fee']  # Tipos específicos mencionados
        
        registros_sin_clasificar = []
        for tipo_mov in tipos_a_reclasificar:
            try:
                batch = ejecutar_con_reintentos(
                    lambda: supabase.table('poker_results').select('*').eq('categoria', 'Torneo').eq('tipo_movimiento', tipo_mov).eq('sala', 'Pokerstars').eq('user_id', str(user_id)).execute()
                )
                if batch.data:
                    registros_sin_clasificar.extend(batch.data)
            except Exception as e:
                print(f"❌ Error obteniendo registros {tipo_mov}: {e}")
                continue
        
        if not registros_sin_clasificar:
            print("⚠️  No se encontraron registros de Pokerstars para reclasificar")
            return 0
        
        print(f"📊 Encontrados {len(registros_sin_clasificar)} registros de Pokerstars para reclasificar")
        
        reclasificados = 0
        for registro in registros_sin_clasificar:
            try:
                descripcion = registro['descripcion']
                
                # Extraer tournament_id de la descripción
                partes = descripcion.split(' ', 1)
                if len(partes) > 0:
                    tournament_id = partes[0]
                    
                    # Buscar en el mapeo de Pokerstars
                    if tournament_id in pokerstars_mapping:
                        mapping_data = pokerstars_mapping[tournament_id]
                        
                        # Actualizar nivel_buyin y tipo_juego si están vacíos o genéricos
                        updates = {}
                        
                        if not registro.get('nivel_buyin') or registro.get('nivel_buyin') == 'null':
                            updates['nivel_buyin'] = mapping_data['nivel_buyin']
                        
                        if not registro.get('tipo_juego') or registro.get('tipo_juego') == 'Torneo':
                            updates['tipo_juego'] = mapping_data['tipo_juego']
                        
                        # Aplicar actualizaciones si hay cambios
                        if updates:
                            try:
                                supabase.table('poker_results').update(updates).eq('id', registro['id']).execute()
                                reclasificados += 1
                                print(f"✅ Pokerstars reclasificado: {registro['tipo_movimiento']} (Torneo: {tournament_id}) -> {updates}")
                            except Exception as e:
                                print(f"⚠️  Error actualizando registro Pokerstars {registro['id']}: {e}")
                                continue
                    else:
                        # Si no encontramos el tournament_id, intentar clasificar por importe para nivel_buyin
                        if not registro.get('nivel_buyin') or registro.get('nivel_buyin') == 'null':
                            try:
                                nivel_calculado = clasificar_nivel_buyin(registro['importe'])
                                supabase.table('poker_results').update({'nivel_buyin': nivel_calculado}).eq('id', registro['id']).execute()
                                reclasificados += 1
                                print(f"✅ Pokerstars clasificado por importe: {registro['tipo_movimiento']} -> nivel: {nivel_calculado}")
                            except Exception as e:
                                print(f"⚠️  Error clasificando por importe {registro['id']}: {e}")
                                continue
                                
            except Exception as e:
                print(f"❌ Error procesando registro Pokerstars {registro['id']}: {e}")
                continue
        
        print(f"✅ Reclasificación de Pokerstars completada: {reclasificados} registros actualizados")
        return reclasificados
        
    except Exception as e:
        print(f"❌ Error en reclasificación automática de Pokerstars: {e}")
        return 0

def reclasificar_tipos_juego_automatica(user_id):
    """Reclasifica automáticamente los tipos de juego para registros relacionados - VERSIÓN SQLITE"""
    try:
        # Obtener todos los registros Buy In con tipo de juego específico
        buyins_clasificados = supabase.table('poker_results').select('*').eq('categoria', 'Torneo').eq('tipo_movimiento', 'Buy In').neq('tipo_juego', 'Torneo').eq('user_id', str(user_id)).execute()
        
        if not buyins_clasificados.data:
            return 0
        
        # Crear diccionario de descripción -> tipo_juego para búsqueda rápida
        descripcion_tipo_juego = {}
        for buyin in buyins_clasificados.data:
            descripcion_tipo_juego[buyin['descripcion']] = buyin['tipo_juego']
        
        # Obtener registros que necesitan reclasificación (solo los que tienen tipo genérico)
        registros_sin_clasificar = supabase.table('poker_results').select('*').eq('categoria', 'Torneo').in_('tipo_movimiento', ['Reentry Buy In', 'Winnings', 'Bounty', 'Fee', 'Reentry Fee', 'Unregister Buy In', 'Unregister Fee', 'Sit & Crush Jackpot', 'Tournament Rebuy', 'Ticket']).eq('tipo_juego', 'Torneo').eq('user_id', str(user_id)).execute()
        
        if not registros_sin_clasificar.data:
            return 0
        
        reclasificados = 0
        for registro in registros_sin_clasificar.data:
            try:
                tipo_juego = None
                
                # Método 1: Búsqueda exacta por descripción
                if registro['descripcion'] in descripcion_tipo_juego:
                    tipo_juego = descripcion_tipo_juego[registro['descripcion']]
                else:
                    # Método 2: Búsqueda por ID del torneo (primeros números)
                    partes = registro['descripcion'].split(' ', 1)
                    if len(partes) > 1:
                        torneo_id = partes[0]
                        
                        # Buscar Buy In que comience con el mismo ID
                        for buyin_desc, tipo in descripcion_tipo_juego.items():
                            if buyin_desc.startswith(torneo_id + ' '):
                                tipo_juego = tipo
                                break
                
                if tipo_juego:
                    # Actualizar registro en Supabase (simple, sin reintentos complejos)
                    try:
                        supabase.table('poker_results').update({'tipo_juego': tipo_juego}).eq('id', registro['id']).execute()
                        reclasificados += 1
                    except Exception as e:
                        print(f"⚠️  Error actualizando registro {registro['id']}: {e}")
                        continue
                    print(f"✅ Reclasificado: {registro['tipo_movimiento']} -> {tipo_juego}")
                    
            except Exception as e:
                print(f"Error reclasificando tipo de juego para registro {registro['id']}: {e}")
                continue
        
        return reclasificados
        
    except Exception as e:
        print(f"Error en reclasificación de tipos de juego: {e}")
        return 0

def procesar_archivo_wpn(filepath, user_id):
    """Procesa archivos Excel de WPN y los importa a Supabase"""
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
        registros_nuevos = []  # Lista para insertar en lotes
        
        total_registros = len(df)
        print(f"Procesando {total_registros} registros...")
        
        for index, row in df.iterrows():
            try:
                # Mostrar progreso cada 50 registros
                if (index + 1) % 50 == 0 or (index + 1) == total_registros:
                    print(f"Progreso: {index + 1}/{total_registros} registros procesados ({((index + 1)/total_registros)*100:.1f}%)")
                
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
                
                # Categorizar automáticamente usando la lógica original probada
                categoria, tipo_movimiento, tipo_juego = categorizar_movimiento(
                    determinar_categoria_pago(payment_method), 
                    payment_method, 
                    descripcion
                )
                
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
                
                # Verificar si ya existe en Supabase
                existing = supabase.table('poker_results').select('id').eq('hash_duplicado', hash_duplicado).eq('user_id', str(user_id)).execute()
                
                if existing.data:
                    duplicados_encontrados += 1
                    # Agregar detalle del duplicado
                    duplicados_detalle.append({
                        'fecha': fecha.isoformat(),
                        'hora': hora.isoformat() if hora else None,
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
                
                # Crear registro para Supabase
                registro = {
                    'id': str(uuid.uuid4()),
                    'user_id': str(user_id),  # Asegurar que sea string
                    'fecha': fecha.isoformat(),
                    'hora': hora.isoformat() if hora else None,
                    'tipo_movimiento': tipo_movimiento,
                    'descripcion': descripcion,
                    'importe': importe,
                    'categoria': categoria,
                    'tipo_juego': tipo_juego,
                    'nivel_buyin': nivel_buyin,
                    'sala': 'WPN',
                    'hash_duplicado': hash_duplicado,
                    'created_at': datetime.now().isoformat()
                }
                
                registros_nuevos.append(registro)
                
                # Insertar en lotes de 100 registros
                if len(registros_nuevos) >= 100:
                    try:
                        supabase.table('poker_results').insert(registros_nuevos).execute()
                        resultados_importados += len(registros_nuevos)
                        print(f"Insertados {len(registros_nuevos)} registros en lote. Total importados: {resultados_importados}")
                        registros_nuevos = []
                    except Exception as e:
                        print(f"Error insertando lote: {e}")
                        # Intentar insertar uno por uno si falla el lote
                        for reg in registros_nuevos:
                            try:
                                supabase.table('poker_results').insert(reg).execute()
                                resultados_importados += 1
                            except Exception as e2:
                                print(f"Error insertando registro individual: {e2}")
                        registros_nuevos = []
                
            except Exception as e:
                errores_procesamiento += 1
                print(f"Error procesando fila {index}: {e}")
                print(f"Datos de la fila: {row.to_dict()}")
                continue
        
        # Insertar registros restantes
        if registros_nuevos:
            try:
                supabase.table('poker_results').insert(registros_nuevos).execute()
                resultados_importados += len(registros_nuevos)
                print(f"Insertados {len(registros_nuevos)} registros finales. Total importados: {resultados_importados}")
            except Exception as e:
                print(f"Error insertando lote final: {e}")
                # Intentar insertar uno por uno si falla el lote
                for reg in registros_nuevos:
                    try:
                        supabase.table('poker_results').insert(reg).execute()
                        resultados_importados += 1
                    except Exception as e2:
                        print(f"Error insertando registro individual final: {e2}")
        
        print(f"Resumen del procesamiento:")
        print(f"- Registros en archivo: {df_original}")
        print(f"- Eliminados por falta de fecha: {df_sin_fecha}")
        print(f"- Errores de procesamiento: {errores_procesamiento}")
        print(f"- Duplicados omitidos: {duplicados_encontrados}")
        print(f"- Registros importados: {resultados_importados}")
        
        # Procesamiento posterior a la importación
        print("Iniciando procesamiento posterior...")
        niveles_reclasificados = reclasificar_niveles_buyin_automatica(user_id)
        tipos_reclasificados = reclasificar_tipos_juego_automatica(user_id)
        print(f"Niveles de buy-in reclasificados: {niveles_reclasificados}")
        print(f"Tipos de juego reclasificados: {tipos_reclasificados}")
        
        return {
            'mensaje': f'Archivo procesado exitosamente. {resultados_importados} registros importados, {duplicados_encontrados} duplicados omitidos.',
            'resultados_importados': resultados_importados,
            'duplicados_encontrados': duplicados_encontrados,
            'duplicados_detalle': duplicados_detalle
        }
        
    except Exception as e:
        return {'error': f'Error procesando archivo WPN: {str(e)}'}

def procesar_archivo_pokerstars(filepath, user_id):
    """Procesa archivos HTML de Pokerstars y los importa a Supabase"""
    try:
        from bs4 import BeautifulSoup
        
        # Leer y parsear HTML
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"Tamaño del archivo HTML: {len(content)} caracteres")
        soup = BeautifulSoup(content, 'html.parser')
        
        # Debug: mostrar todas las tablas encontradas
        todas_las_tablas = soup.find_all('table')
        debug_info = f"Total de tablas encontradas en el HTML: {len(todas_las_tablas)}"
        print(debug_info)
        
        for i, tabla in enumerate(todas_las_tablas):
            filas = tabla.find_all('tr')
            tabla_info = f"Tabla {i+1}: {len(filas)} filas"
            print(tabla_info)
            debug_info += f"\n{tabla_info}"
            if filas:
                primera_fila = filas[0].find_all(['th', 'td'])
                fila_info = f"  Primera fila: {[celda.get_text().strip() for celda in primera_fila]}"
                print(fila_info)
                debug_info += f"\n{fila_info}"
        
        # Buscar tabla de transacciones con múltiples selectores
        tabla = None
        
        # Intentar diferentes selectores de tabla
        selectores = [
            {'class': 'table'},
            {'class': 'dataTable'},
            {'class': 'transactions'},
            {'id': 'transactions'},
            {'id': 'dataTable'},
            {}  # Cualquier tabla
        ]
        
        for selector in selectores:
            tabla = soup.find('table', selector)
            if tabla:
                print(f"Tabla encontrada con selector: {selector}")
                break
        
        if not tabla:
            # Buscar cualquier tabla en el documento
            tablas = soup.find_all('table')
            if tablas:
                tabla = tablas[0]  # Usar la primera tabla encontrada
                print("Usando la primera tabla encontrada en el documento")
            else:
                raise Exception("No se encontró ninguna tabla en el archivo HTML")
        
        resultados_importados = 0
        duplicados_encontrados = 0
        duplicados_detalle = []
        registros_nuevos = []  # Lista para insertar en lotes
        
        # Procesar filas de la tabla
        filas = tabla.find_all('tr')
        print(f"Total de filas encontradas en la tabla: {len(filas)}")
        
        # Detectar si hay encabezado
        if filas and filas[0].find_all(['th', 'td']):
            # Verificar si la primera fila parece ser un encabezado
            primera_fila = filas[0].find_all(['th', 'td'])
            if primera_fila and any('date' in celda.get_text().lower() or 'fecha' in celda.get_text().lower() for celda in primera_fila):
                filas = filas[1:]  # Saltar encabezado
                print("Encabezado detectado y omitido")
        
        total_registros = len(filas)
        print(f"Procesando {total_registros} registros de Pokerstars...")
        
        if total_registros == 0:
            print("No se encontraron filas de datos en la tabla")
            return {
                'mensaje': f'No se encontraron registros de transacciones en el archivo HTML.\nDebug: {debug_info}',
                'resultados_importados': 0,
                'duplicados_encontrados': 0,
                'duplicados_detalle': [],
                'debug_info': debug_info
            }
        
        registros_procesados = 0
        registros_omitidos = 0
        
        for index, fila in enumerate(filas):
            try:
                # Mostrar progreso cada 50 registros
                if (index + 1) % 50 == 0 or (index + 1) == total_registros:
                    print(f"Progreso: {index + 1}/{total_registros} registros procesados ({((index + 1)/total_registros)*100:.1f}%)")
                
                celdas = fila.find_all(['td', 'th'])
                if len(celdas) < 3:  # Mínimo 3 columnas
                    registros_omitidos += 1
                    if index < 5:  # Mostrar solo los primeros 5 para debug
                        print(f"Fila {index + 1} omitida: solo {len(celdas)} columnas")
                    continue
                
                # Extraer datos de las celdas - adaptarse a diferentes formatos
                if len(celdas) >= 4:
                    # Formato estándar: fecha, tipo, descripción, importe
                    fecha_str = celdas[0].get_text().strip()
                    tipo = celdas[1].get_text().strip()
                    descripcion = celdas[2].get_text().strip()
                    importe_str = celdas[3].get_text().strip()
                elif len(celdas) == 3:
                    # Formato alternativo: fecha, descripción, importe
                    fecha_str = celdas[0].get_text().strip()
                    descripcion = celdas[1].get_text().strip()
                    importe_str = celdas[2].get_text().strip()
                    tipo = "Transaction"  # Tipo por defecto
                else:
                    continue
                
                # Validar que tenemos datos esenciales
                if not fecha_str or not importe_str:
                    registros_omitidos += 1
                    if index < 5:  # Mostrar solo los primeros 5 para debug
                        print(f"Fila {index + 1} omitida: fecha='{fecha_str}', importe='{importe_str}'")
                    continue
                
                registros_procesados += 1
                if index < 5:  # Mostrar solo los primeros 5 para debug
                    print(f"Fila {index + 1} procesada: fecha='{fecha_str}', tipo='{tipo}', desc='{descripcion[:50]}...', importe='{importe_str}'")
                
                # Procesar fecha
                try:
                    fecha = pd.to_datetime(fecha_str).date()
                except Exception as e:
                    print(f"Error procesando fecha '{fecha_str}': {e}")
                    continue
                
                # Procesar importe
                try:
                    # Limpiar el importe de símbolos y comas
                    importe_limpio = importe_str.replace('$', '').replace(',', '').replace('€', '').replace('£', '').strip()
                    importe = float(importe_limpio)
                except Exception as e:
                    print(f"Error procesando importe '{importe_str}': {e}")
                    continue
                
                # Categorizar movimiento usando la lógica original probada
                categoria, tipo_movimiento, tipo_juego = categorizar_movimiento_pokerstars(
                    tipo, 
                    None,  # No hay columna Game en este formato
                    None   # No hay tournament_id en este formato
                )
                
                # Generar hash para duplicados
                hash_duplicado = generar_hash_duplicado(
                    fecha, 
                    None,  # No hay hora específica en Pokerstars
                    tipo,
                    descripcion,
                    importe,
                    0,  # No hay money_out en Pokerstars
                    'Pokerstars'
                )
                
                # Verificar duplicados en Supabase
                existing = supabase.table('poker_results').select('id').eq('hash_duplicado', hash_duplicado).eq('user_id', str(user_id)).execute()
                
                if existing.data:
                    duplicados_encontrados += 1
                    duplicados_detalle.append({
                        'fecha': fecha.isoformat(),
                        'tipo_movimiento': tipo_movimiento,
                        'descripcion': descripcion,
                        'importe': importe,
                        'categoria': categoria,
                        'tipo_juego': tipo_juego
                    })
                    continue
                
                # Crear registro para Supabase
                registro = {
                    'id': str(uuid.uuid4()),
                    'user_id': str(user_id),  # Asegurar que sea string
                    'fecha': fecha.isoformat(),
                    'tipo_movimiento': tipo_movimiento,
                    'descripcion': descripcion,
                    'importe': importe,
                    'categoria': categoria,
                    'tipo_juego': tipo_juego,
                    'sala': 'Pokerstars',
                    'hash_duplicado': hash_duplicado,
                    'created_at': datetime.now().isoformat()
                }
                
                registros_nuevos.append(registro)
                
                # Insertar en lotes de 100 registros
                if len(registros_nuevos) >= 100:
                    try:
                        supabase.table('poker_results').insert(registros_nuevos).execute()
                        resultados_importados += len(registros_nuevos)
                        print(f"Insertados {len(registros_nuevos)} registros en lote. Total importados: {resultados_importados}")
                        registros_nuevos = []
                    except Exception as e:
                        print(f"Error insertando lote: {e}")
                        # Intentar insertar uno por uno si falla el lote
                        for reg in registros_nuevos:
                            try:
                                supabase.table('poker_results').insert(reg).execute()
                                resultados_importados += 1
                            except Exception as e2:
                                print(f"Error insertando registro individual: {e2}")
                        registros_nuevos = []
                
            except Exception as e:
                print(f"Error procesando fila {index}: {e}")
                continue
        
        # Insertar registros restantes
        if registros_nuevos:
            try:
                supabase.table('poker_results').insert(registros_nuevos).execute()
                resultados_importados += len(registros_nuevos)
                print(f"Insertados {len(registros_nuevos)} registros finales. Total importados: {resultados_importados}")
            except Exception as e:
                print(f"Error insertando lote final: {e}")
                # Intentar insertar uno por uno si falla el lote
                for reg in registros_nuevos:
                    try:
                        supabase.table('poker_results').insert(reg).execute()
                        resultados_importados += 1
                    except Exception as e2:
                        print(f"Error insertando registro individual final: {e2}")
        
        print(f"Resumen del procesamiento Pokerstars:")
        print(f"- Registros en archivo: {total_registros}")
        print(f"- Registros procesados: {registros_procesados}")
        print(f"- Registros omitidos: {registros_omitidos}")
        print(f"- Duplicados omitidos: {duplicados_encontrados}")
        print(f"- Registros importados: {resultados_importados}")
        
        if resultados_importados == 0 and registros_procesados == 0:
            print(f"Debug info: {debug_info}")
        
        # Procesamiento posterior a la importación
        print("Iniciando procesamiento posterior...")
        niveles_reclasificados = reclasificar_niveles_buyin_automatica(user_id)
        tipos_reclasificados = reclasificar_tipos_juego_automatica(user_id)
        print(f"Niveles de buy-in reclasificados: {niveles_reclasificados}")
        print(f"Tipos de juego reclasificados: {tipos_reclasificados}")
        
        return {
            'mensaje': f'Archivo procesado exitosamente. {resultados_importados} registros importados, {duplicados_encontrados} duplicados omitidos.',
            'resultados_importados': resultados_importados,
            'duplicados_encontrados': duplicados_encontrados,
            'duplicados_detalle': duplicados_detalle
        }
        
    except Exception as e:
        return {'error': f'Error procesando archivo Pokerstars: {str(e)}'}

def procesar_archivo_wpn_con_progreso_streaming(filepath, user_id, progress_callback):
    """Procesa archivos Excel de WPN con streaming de progreso en tiempo real"""
    try:
        # Leer el archivo Excel
        df = pd.read_excel(filepath)
        print(f"Total registros en archivo: {len(df)}")
        
        # Limpiar y procesar los datos
        df_original = len(df)
        df = df.dropna(subset=['Date'])  # Eliminar filas sin fecha
        df_sin_fecha = df_original - len(df)
        print(f"Registros eliminados por falta de fecha: {df_sin_fecha}")
        
        total_registros = len(df)
        print(f"Procesando {total_registros} registros...")
        
        # Enviar mensaje inicial
        yield f"data: {json.dumps({'tipo': 'inicio', 'total_registros': total_registros})}\n\n"
        
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
                    
                    # Enviar progreso inmediatamente
                    progress_data = {
                        'tipo': 'progreso', 
                        'procesados': index + 1, 
                        'total': total_registros, 
                        'porcentaje': porcentaje, 
                        'etapa': 'procesando'
                    }
                    yield f"data: {json.dumps(progress_data)}\n\n"
                
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
                
                # Determinar importe (Money In - Money Out) con límite para evitar overflow
                importe = money_in - money_out
                # Limitar importe a un rango seguro para evitar overflow numérico en Supabase
                if abs(importe) > 999999.99:
                    importe = 999999.99 if importe > 0 else -999999.99
                    print(f"⚠️  Importe limitado: {importe} (original: {money_in - money_out})")
                
                # Categorizar automáticamente usando la lógica original probada
                categoria, tipo_movimiento, tipo_juego = categorizar_movimiento(
                    determinar_categoria_pago(payment_method), 
                    payment_method,
                    descripcion
                )
                
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
                
                # Calcular nivel de buy-in SOLO para registros Buy In
                nivel_buyin = None
                if categoria == 'Torneo' and tipo_movimiento == 'Buy In':
                    nivel_buyin = clasificar_nivel_buyin(importe)
                
                # Crear registro para Supabase
                registro = {
                    'id': str(uuid.uuid4()),
                    'user_id': str(user_id),
                    'fecha': fecha.isoformat(),
                    'hora': hora.isoformat() if hora else None,
                    'tipo_movimiento': tipo_movimiento,
                    'descripcion': descripcion,
                    'importe': round(importe, 2),  # Redondear a 2 decimales
                    'categoria': categoria,
                    'tipo_juego': tipo_juego,
                    'nivel_buyin': nivel_buyin,
                    'sala': 'WPN',
                    'hash_duplicado': hash_duplicado
                }
                
                registros_nuevos.append(registro)
                
            except Exception as e:
                print(f"Error procesando fila {index}: {e}")
                errores_procesamiento += 1
                continue
        
        # Insertar registros en lotes de 200 para optimizar rendimiento
        print(f"📦 Insertando {len(registros_nuevos)} registros en lotes de 200...")
        lote_size = 200
        total_lotes = (len(registros_nuevos) + lote_size - 1) // lote_size
        
        for i in range(0, len(registros_nuevos), lote_size):
            lote = registros_nuevos[i:i + lote_size]
            
            try:
                # Insertar lote en Supabase
                supabase.table('poker_results').insert(lote).execute()
                resultados_importados += len(lote)
                
                # Calcular progreso de inserción
                registros_procesados = min(i + lote_size, len(registros_nuevos))
                porcentaje_insercion = (registros_procesados / len(registros_nuevos)) * 100
                
                # Enviar progreso de inserción
                lote_data = {
                    'tipo': 'lote_completado',
                    'procesados': registros_procesados,
                    'total': len(registros_nuevos),
                    'porcentaje': porcentaje_insercion,
                    'lote_size': len(lote),
                    'etapa': 'insertando'
                }
                yield f"data: {json.dumps(lote_data)}\n\n"
                
                print(f"✅ Lote {i//lote_size + 1}/{total_lotes} insertado: {len(lote)} registros")
                
            except Exception as e:
                print(f"❌ Error insertando lote: {e}")
                errores_procesamiento += len(lote)
        
        # Retornar resultado final
        mensaje = f'Archivo procesado exitosamente. {resultados_importados} registros importados, {duplicados_encontrados} duplicados omitidos.'
        if errores_procesamiento > 0:
            mensaje += f' {errores_procesamiento} errores durante el procesamiento.'
        
        resultado_final = {
            'tipo': 'completado',
            'mensaje': mensaje,
            'resultados_importados': resultados_importados,
            'duplicados_encontrados': duplicados_encontrados,
            'duplicados_detalle': duplicados_detalle,
            'errores_procesamiento': errores_procesamiento
        }
        
        yield f"data: {json.dumps(resultado_final)}\n\n"
        
        # Ejecutar reclasificación automática después de la importación
        try:
            print("🔄 Iniciando reclasificación automática...")
            
            # Reclasificar niveles de buy-in
            reclasificados_buyin = reclasificar_niveles_buyin_automatica(user_id)
            if reclasificados_buyin > 0:
                print(f"✅ Reclasificados {reclasificados_buyin} registros por nivel de buy-in")
            
            # Reclasificar tipos de juego
            reclasificados_juego = reclasificar_tipos_juego_automatica(user_id)
            if reclasificados_juego > 0:
                print(f"✅ Reclasificados {reclasificados_juego} registros por tipo de juego")
                
        except Exception as e:
            print(f"⚠️  Error en reclasificación automática: {e}")
        
        return resultado_final
        
    except Exception as e:
        error_msg = f'Error procesando archivo WPN: {str(e)}'
        print(error_msg)
        yield f"data: {json.dumps({'error': error_msg})}\n\n"
        return {'error': error_msg}

def procesar_archivo_wpn_con_progreso(filepath, user_id, progress_callback):
    """Procesa archivos Excel de WPN con inserción masiva optimizada"""
    try:
        # Leer el archivo Excel
        df = pd.read_excel(filepath)
        print(f"Total registros en archivo: {len(df)}")
        
        # Limpiar y procesar los datos
        df_original = len(df)
        df = df.dropna(subset=['Date'])  # Eliminar filas sin fecha
        df_sin_fecha = df_original - len(df)
        print(f"Registros eliminados por falta de fecha: {df_sin_fecha}")
        
        total_registros = len(df)
        print(f"Procesando {total_registros} registros...")
        
        # Enviar total de registros al cliente
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
                    
                    # Enviar progreso al cliente
                    progress_callback(f"data: {json.dumps({'tipo': 'progreso', 'procesados': index + 1, 'total': total_registros, 'porcentaje': porcentaje, 'etapa': 'procesando'})}\n\n")
                
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
                
                # Determinar importe (Money In - Money Out) con límite para evitar overflow
                importe = money_in - money_out
                # Limitar importe a un rango seguro para evitar overflow numérico en Supabase
                if abs(importe) > 999999.99:
                    importe = 999999.99 if importe > 0 else -999999.99
                    print(f"⚠️  Importe limitado: {importe} (original: {money_in - money_out})")
                
                # Categorizar automáticamente usando la lógica original probada
                categoria, tipo_movimiento, tipo_juego = categorizar_movimiento(
                    determinar_categoria_pago(payment_method), 
                    payment_method, 
                    descripcion
                )
                
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
                
                # Calcular nivel de buy-in SOLO para registros Buy In
                nivel_buyin = None
                if categoria == 'Torneo' and tipo_movimiento == 'Buy In':
                    nivel_buyin = clasificar_nivel_buyin(importe)
                
                # Crear registro para Supabase
                registro = {
                    'id': str(uuid.uuid4()),
                    'user_id': str(user_id),
                    'fecha': fecha.isoformat(),
                    'hora': hora.isoformat() if hora else None,
                    'tipo_movimiento': tipo_movimiento,
                    'descripcion': descripcion,
                    'importe': round(importe, 2),  # Redondear a 2 decimales
                    'categoria': categoria,
                    'tipo_juego': tipo_juego,
                    'nivel_buyin': nivel_buyin,
                    'sala': 'WPN',
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
                    
                    # Enviar avance del lote al cliente
                    porcentaje_lote = (resultados_importados / len(registros_sin_duplicados)) * 100
                    progress_callback(f"data: {json.dumps({'tipo': 'lote_completado', 'procesados': resultados_importados, 'total': len(registros_sin_duplicados), 'porcentaje': porcentaje_lote, 'lote_size': len(lote), 'etapa': 'insertando'})}\n\n")
                    
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
        
        # Procesamiento posterior a la importación
        print("🔄 Iniciando procesamiento posterior...")
        niveles_reclasificados = reclasificar_niveles_buyin_automatica(user_id)
        tipos_reclasificados = reclasificar_tipos_juego_automatica(user_id)
        print(f"✅ Niveles de buy-in reclasificados: {niveles_reclasificados}")
        print(f"✅ Tipos de juego reclasificados: {tipos_reclasificados}")
        
        return {
            'mensaje': f'Archivo procesado exitosamente. {resultados_importados} registros importados, {duplicados_encontrados} duplicados omitidos.',
            'resultados_importados': resultados_importados,
            'duplicados_encontrados': duplicados_encontrados,
            'duplicados_detalle': duplicados_detalle
        }
        
    except Exception as e:
        return {'error': f'Error procesando archivo WPN: {str(e)}'}

def procesar_archivo_pokerstars_con_progreso_streaming(filepath, user_id, progress_callback):
    """Procesa archivos HTML de Pokerstars con streaming de progreso - BASADO EN LA IMPLEMENTACIÓN QUE FUNCIONABA EN SQLITE"""
    try:
        import pandas as pd
        from bs4 import BeautifulSoup
        
        # Leer y parsear HTML
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"Tamaño del archivo HTML: {len(content)} caracteres")
        soup = BeautifulSoup(content, 'html.parser')
        table = soup.find('table')
        
        if not table:
            error_msg = "No se encontró tabla en el archivo"
            yield f"data: {json.dumps({'error': error_msg})}\n\n"
            return {'error': error_msg}
        
        # Obtener filas
        rows = table.find_all('tr')
        if len(rows) < 3:
            error_msg = "Archivo no tiene suficientes filas"
            yield f"data: {json.dumps({'error': error_msg})}\n\n"
            return {'error': error_msg}
        
        # Headers (segunda fila) - como en la implementación que funcionaba
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
            error_msg = "No se encontraron datos en el archivo"
            yield f"data: {json.dumps({'error': error_msg})}\n\n"
            return {'error': error_msg}
        
        df = pd.DataFrame(data, columns=subheaders)
        total_registros = len(df)
        
        # Enviar mensaje inicial
        yield f"data: {json.dumps({'tipo': 'inicio', 'total_registros': total_registros})}\n\n"
        
        resultados_importados = 0
        duplicados_encontrados = 0
        errores_procesamiento = 0
        duplicados_detalle = []
        registros_nuevos = []
        
        print(f"Procesando {total_registros} registros de Pokerstars usando DataFrame...")
        
        for index, row in df.iterrows():
            try:
                # Mostrar progreso cada 100 registros
                if (index + 1) % 100 == 0 or (index + 1) == total_registros:
                    porcentaje = ((index + 1) / total_registros) * 100
                    print(f"Progreso: {index + 1}/{total_registros} registros procesados ({porcentaje:.1f}%)")
                    
                    # Enviar progreso inmediatamente
                    progress_data = {
                        'tipo': 'progreso', 
                        'procesados': index + 1, 
                        'total': total_registros, 
                        'porcentaje': porcentaje, 
                        'etapa': 'procesando'
                    }
                    yield f"data: {json.dumps(progress_data)}\n\n"
                
                # Extraer datos básicos - usar las columnas específicas de PokerStars como en la implementación que funcionaba
                fecha_str = str(row.get('Date/Time', ''))
                action = str(row.get('Action', ''))
                game = str(row.get('Game', ''))
                amount_str = str(row.get('Amount', ''))
                tournament_id = str(row.get('Table Name / Player / Tournament #', ''))
                
                if not fecha_str or not action or fecha_str == 'nan' or action == 'nan':
                    errores_procesamiento += 1
                    continue
                
                # Parsear fecha y hora - como en la implementación que funcionaba
                try:
                    fecha_dt = pd.to_datetime(fecha_str, format='%Y/%m/%d %I:%M %p')
                    fecha = fecha_dt.date()
                    hora = fecha_dt.time()
                except Exception as e:
                    print(f"⚠️  Error procesando fecha '{fecha_str}': {e}")
                    errores_procesamiento += 1
                    continue
                
                # Parsear importe - como en la implementación que funcionaba
                try:
                    amount_clean = amount_str.replace('(', '-').replace(')', '').replace(',', '')
                    importe = float(amount_clean)
                except Exception as e:
                    print(f"⚠️  Error procesando importe '{amount_str}': {e}")
                    errores_procesamiento += 1
                    continue
                
                # Categorizar movimiento - como en la implementación que funcionaba
                categoria, tipo_movimiento, tipo_juego = categorizar_movimiento_pokerstars(action, game, tournament_id)
                
                # Crear descripción - como en la implementación que funcionaba
                descripcion = f"{tournament_id} {game}".strip()
                if not descripcion or descripcion == tournament_id:
                    descripcion = f"{tournament_id} {action}"
                
                # Generar hash para duplicados - como en la implementación que funcionaba
                hash_duplicado = generar_hash_duplicado(fecha, hora, action, descripcion, importe, 0, 'Pokerstars')
                
                # Calcular nivel de buy-in para torneos - como en la implementación que funcionaba
                nivel_buyin = None
                if categoria == 'Torneo' and tipo_movimiento == 'Buy In':
                    nivel_buyin = clasificar_nivel_buyin(importe)
                
                # Crear registro para Supabase
                registro = {
                    'fecha': fecha.isoformat(),
                    'hora': hora.isoformat() if hora else None,
                    'tipo_movimiento': tipo_movimiento,
                    'descripcion': descripcion,
                    'importe': importe,
                    'categoria': categoria,
                    'tipo_juego': tipo_juego,
                    'nivel_buyin': nivel_buyin,
                    'sala': 'Pokerstars',
                    'user_id': str(user_id),
                    'hash_duplicado': hash_duplicado
                }
                
                registros_nuevos.append(registro)
                
            except Exception as e:
                print(f"Error procesando fila {index}: {e}")
                errores_procesamiento += 1
                continue
        
        # Verificar duplicados en lote (lógica correcta de SQLite)
        print("🔍 Verificando duplicados...")
        hashes_existentes = set()
        if registros_nuevos:
            # Obtener todos los hashes existentes de una vez
            try:
                existing_hashes = ejecutar_con_reintentos(
                    lambda: supabase.table('poker_results').select('hash_duplicado').eq('user_id', str(user_id)).execute()
                )
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
            print(f"📦 Insertando {len(registros_sin_duplicados)} registros en lotes de 200...")
            lote_size = 200
            
            for i in range(0, len(registros_sin_duplicados), lote_size):
                lote = registros_sin_duplicados[i:i + lote_size]
                
                try:
                    ejecutar_con_reintentos(lambda: supabase.table('poker_results').insert(lote).execute())
                    resultados_importados += len(lote)
                    
                    # Calcular progreso de inserción
                    registros_procesados = min(i + lote_size, len(registros_sin_duplicados))
                    porcentaje_insercion = (registros_procesados / len(registros_sin_duplicados)) * 100
                    
                    # Enviar progreso de inserción
                    lote_data = {
                        'tipo': 'lote_completado',
                        'procesados': registros_procesados,
                        'total': len(registros_sin_duplicados),
                        'porcentaje': porcentaje_insercion,
                        'lote_size': len(lote),
                        'etapa': 'insertando'
                    }
                    yield f"data: {json.dumps(lote_data)}\n\n"
                    
                except Exception as e:
                    print(f"❌ Error insertando lote: {e}")
                    errores_procesamiento += len(lote)
        
                # Ejecutar reclasificación automática después de la importación (Pokerstars específica)
                try:
                    print("🔄 Iniciando reclasificación automática de Pokerstars...")
                    
                    # Reclasificación específica de Pokerstars que busca Buy In padre
                    reclasificados_pokerstars = reclasificar_pokerstars_automatica(user_id)
                    if reclasificados_pokerstars > 0:
                        print(f"✅ Reclasificados {reclasificados_pokerstars} registros de Pokerstars usando Buy In padre")
                    
                    # Reclasificación general de niveles de buy-in como fallback
                    reclasificados_niveles = reclasificar_niveles_buyin_automatica(user_id)
                    if reclasificados_niveles > 0:
                        print(f"✅ Reclasificados {reclasificados_niveles} registros por nivel de buy-in general")
                    
                    # Reclasificación general de tipos de juego
                    reclasificados_tipos = reclasificar_tipos_juego_automatica(user_id)
                    if reclasificados_tipos > 0:
                        print(f"✅ Reclasificados {reclasificados_tipos} registros por tipo de juego")
                        
                except Exception as e:
                    print(f"⚠️  Error en reclasificación automática: {e}")
        
        # Resultado final
        mensaje = f'Archivo procesado exitosamente. {resultados_importados} registros importados, {duplicados_encontrados} duplicados omitidos.'
        if errores_procesamiento > 0:
            mensaje += f' {errores_procesamiento} errores durante el procesamiento.'
        
        resultado_final = {
            'tipo': 'completado',
            'mensaje': mensaje,
            'resultados_importados': resultados_importados,
            'duplicados_encontrados': duplicados_encontrados,
            'duplicados_detalle': duplicados_detalle,
            'errores_procesamiento': errores_procesamiento
        }
        
        yield f"data: {json.dumps(resultado_final)}\n\n"
        return resultado_final
        
    except Exception as e:
        error_msg = f'Error procesando archivo Pokerstars: {str(e)}'
        print(error_msg)
        yield f"data: {json.dumps({'error': error_msg})}\n\n"
        return {'error': error_msg}

def procesar_archivo_pokerstars_excel_con_progreso_streaming(filepath, user_id, progress_callback):
    """Procesa archivos Excel de PokerStars con progreso en tiempo real - BASADO EN LA IMPLEMENTACIÓN QUE YA FUNCIONABA"""
    try:
        import pandas as pd
        
        # Leer archivo Excel con motor específico
        try:
            df = pd.read_excel(filepath, engine='openpyxl')
        except:
            try:
                df = pd.read_excel(filepath, engine='xlrd')
            except:
                df = pd.read_excel(filepath)
        
        total_registros = len(df)
        print(f"📊 Total registros en archivo Excel: {total_registros}")
        
        if total_registros == 0:
            error_msg = 'No se encontraron registros en el archivo Excel'
            print(error_msg)
            yield f"data: {json.dumps({'error': error_msg})}\n\n"
            return {'error': error_msg}
        
        # Enviar inicio
        yield f"data: {json.dumps({'tipo': 'inicio', 'total_registros': total_registros})}\n\n"
        
        resultados_importados = 0
        duplicados_encontrados = 0
        errores_procesamiento = 0
        duplicados_detalle = []
        registros_nuevos = []
        
        # Procesar cada registro
        for index, row in df.iterrows():
            try:
                # Mostrar progreso cada 50 registros
                if (index + 1) % 50 == 0 or (index + 1) == total_registros:
                    porcentaje = ((index + 1) / total_registros) * 100
                    print(f"Progreso: {index + 1}/{total_registros} registros procesados ({porcentaje:.1f}%)")
                    
                    # Enviar progreso
                    yield f"data: {json.dumps({'tipo': 'progreso', 'procesados': index + 1, 'total': total_registros, 'porcentaje': porcentaje, 'etapa': 'procesando'})}\n\n"
                
                # Extraer datos básicos - usar las columnas que ya funcionaban
                fecha_str = str(row.get('Date/Time', ''))
                action = str(row.get('Action', ''))
                game = str(row.get('Game', ''))
                amount_str = str(row.get('Amount', ''))
                tournament_id = str(row.get('Table Name / Player / Tournament #', ''))
                
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
                
                # Parsear importe - limpiar formato de PokerStars
                try:
                    amount_clean = amount_str.replace('(', '-').replace(')', '').replace(',', '').replace('$', '').strip()
                    importe = float(amount_clean)
                except Exception as e:
                    print(f"⚠️  Error procesando importe '{amount_str}': {e}")
                    errores_procesamiento += 1
                    continue
                
                # Categorizar movimiento usando la función específica de PokerStars
                categoria, tipo_movimiento, tipo_juego = categorizar_movimiento_pokerstars(action, game, tournament_id)
                
                # Crear descripción
                descripcion = f"{tournament_id} {game}".strip()
                if not descripcion or descripcion == tournament_id:
                    descripcion = f"{tournament_id} {action}"
                
                # Generar hash para duplicados
                hash_duplicado = generar_hash_duplicado(
                    fecha, 
                    hora, 
                    action,
                    descripcion,
                    importe if importe > 0 else 0,
                    abs(importe) if importe < 0 else 0,
                    'Pokerstars'
                )
                
                # Crear registro
                registro = {
                    'fecha': fecha.isoformat(),
                    'hora': hora.isoformat() if hora else None,
                    'sala': 'Pokerstars',
                    'categoria': categoria,
                    'tipo_movimiento': tipo_movimiento,
                    'tipo_juego': tipo_juego,
                    'nivel_buyin': clasificar_nivel_buyin(importe),
                    'descripcion': descripcion,
                    'importe': importe,
                    'user_id': str(user_id),
                    'hash_duplicado': hash_duplicado
                }
                
                registros_nuevos.append(registro)
                
            except Exception as e:
                print(f"❌ Error procesando registro {index + 1}: {e}")
                errores_procesamiento += 1
                continue
        
        print(f"📊 Registros procesados: {len(registros_nuevos)}")
        print(f"📊 Errores: {errores_procesamiento}")
        
        # Verificar duplicados en lote
        print("🔍 Verificando duplicados...")
        hashes_existentes = set()
        if registros_nuevos:
            try:
                existing_hashes = ejecutar_con_reintentos(
                    lambda: supabase.table('poker_results').select('hash_duplicado').eq('user_id', str(user_id)).execute()
                )
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
        
        # Insertar registros nuevos en lotes
        if registros_sin_duplicados:
            print(f"📦 Insertando {len(registros_sin_duplicados)} registros en lotes de 200...")
            lote_size = 200
            
            for i in range(0, len(registros_sin_duplicados), lote_size):
                lote = registros_sin_duplicados[i:i + lote_size]
                
                try:
                    ejecutar_con_reintentos(lambda: supabase.table('poker_results').insert(lote).execute())
                    resultados_importados += len(lote)
                    
                    # Calcular progreso de inserción
                    registros_procesados = min(i + lote_size, len(registros_sin_duplicados))
                    porcentaje_insercion = (registros_procesados / len(registros_sin_duplicados)) * 100
                    
                    # Enviar progreso de inserción
                    lote_data = {
                        'tipo': 'lote_completado',
                        'procesados': registros_procesados,
                        'total': len(registros_sin_duplicados),
                        'porcentaje': porcentaje_insercion,
                        'lote_size': len(lote),
                        'etapa': 'insertando'
                    }
                    yield f"data: {json.dumps(lote_data)}\n\n"
                    
                except Exception as e:
                    print(f"❌ Error insertando lote: {e}")
                    errores_procesamiento += len(lote)
        
        # Resultado final
        mensaje = f'Archivo Excel de PokerStars procesado exitosamente. {resultados_importados} registros importados, {duplicados_encontrados} duplicados omitidos.'
        if errores_procesamiento > 0:
            mensaje += f' {errores_procesamiento} errores durante el procesamiento.'
        
        resultado_final = {
            'tipo': 'completado',
            'mensaje': mensaje,
            'resultados_importados': resultados_importados,
            'duplicados_encontrados': duplicados_encontrados,
            'duplicados_detalle': duplicados_detalle,
            'errores_procesamiento': errores_procesamiento
        }
        
        yield f"data: {json.dumps(resultado_final)}\n\n"
        
        # Ejecutar reclasificación automática de Pokerstars (igual que en HTML)
        try:
            print("🔄 Iniciando reclasificación automática de Pokerstars Excel...")
            
            # Reclasificación específica de Pokerstars que busca Buy In padre
            reclasificados_pokerstars = reclasificar_pokerstars_automatica(user_id)
            if reclasificados_pokerstars > 0:
                print(f"✅ Reclasificados {reclasificados_pokerstars} registros de Pokerstars usando Buy In padre")
            
            # Reclasificación general de niveles de buy-in como fallback
            reclasificados_niveles = reclasificar_niveles_buyin_automatica(user_id)
            if reclasificados_niveles > 0:
                print(f"✅ Reclasificados {reclasificados_niveles} registros por nivel de buy-in general")
            
            # Reclasificación general de tipos de juego
            reclasificados_tipos = reclasificar_tipos_juego_automatica(user_id)
            if reclasificados_tipos > 0:
                print(f"✅ Reclasificados {reclasificados_tipos} registros por tipo de juego")
                
        except Exception as e:
            print(f"⚠️  Error en reclasificación automática: {e}")
        
        return resultado_final
        
    except Exception as e:
        error_msg = f'Error procesando archivo Excel de PokerStars: {str(e)}'
        print(error_msg)
        yield f"data: {json.dumps({'error': error_msg})}\n\n"
        return {'error': error_msg}

def procesar_archivo_pokerstars_con_progreso(filepath, user_id, progress_callback):
    """Procesa archivos HTML de Pokerstars con inserción masiva optimizada"""
    try:
        # Leer archivo HTML
        with open(filepath, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Buscar tabla de transacciones con múltiples selectores
        tabla = None
        selectores = [
            'table[data-testid="transactions-table"]',
            'table.transactions',
            'table.dataTable',
            'table[class*="transaction"]',
            'table[class*="history"]',
            'table'
        ]
        
        for selector in selectores:
            tabla = soup.select_one(selector)
            if tabla:
                print(f"✅ Tabla encontrada con selector: {selector}")
                break
        
        if not tabla:
            return {'error': 'No se encontró tabla de transacciones en el archivo HTML'}
        
        # Obtener filas de la tabla
        filas = tabla.find_all('tr')
        print(f"Total filas encontradas: {len(filas)}")
        
        # Filtrar filas que contengan datos (no headers)
        filas_datos = []
        for fila in filas:
            celdas = fila.find_all(['td', 'th'])
            if len(celdas) >= 3:  # Mínimo 3 columnas
                # Verificar si es header (contiene texto como "Date", "Description", etc.)
                texto_celdas = [celda.get_text(strip=True).lower() for celda in celdas]
                if not any(palabra in ' '.join(texto_celdas) for palabra in ['date', 'description', 'amount', 'type', 'fecha', 'descripción', 'importe', 'tipo']):
                    filas_datos.append(fila)
        
        total_registros = len(filas_datos)
        print(f"Total registros a procesar: {total_registros}")
        
        if total_registros == 0:
            return {'error': 'No se encontraron registros válidos en la tabla'}
        
        # Enviar total de registros al cliente
        progress_callback(f"data: {json.dumps({'tipo': 'inicio', 'total_registros': total_registros})}\n\n")
        
        resultados_importados = 0
        duplicados_encontrados = 0
        errores_procesamiento = 0
        duplicados_detalle = []
        registros_nuevos = []
        
        # Procesar todos los registros primero
        print("🔄 Procesando registros...")
        for index, fila in enumerate(filas_datos):
            try:
                # Mostrar progreso cada 100 registros
                if (index + 1) % 100 == 0 or (index + 1) == total_registros:
                    porcentaje = ((index + 1) / total_registros) * 100
                    print(f"Progreso: {index + 1}/{total_registros} registros procesados ({porcentaje:.1f}%)")
                    
                    # Enviar progreso al cliente
                    progress_callback(f"data: {json.dumps({'tipo': 'progreso', 'procesados': index + 1, 'total': total_registros, 'porcentaje': porcentaje, 'etapa': 'procesando'})}\n\n")
                
                celdas = fila.find_all(['td', 'th'])
                if len(celdas) < 3:
                    continue
                
                # Extraer datos de las celdas
                fecha_str = celdas[0].get_text(strip=True)
                descripcion = celdas[1].get_text(strip=True)
                importe_str = celdas[2].get_text(strip=True)
                tipo_str = celdas[3].get_text(strip=True) if len(celdas) > 3 else ''
                
                # Procesar fecha
                try:
                    fecha = pd.to_datetime(fecha_str).date()
                except:
                    continue
                
                # Procesar importe
                try:
                    # Limpiar símbolos de moneda y espacios
                    importe_limpio = importe_str.replace('$', '').replace(',', '').replace('€', '').replace('£', '').strip()
                    importe = float(importe_limpio)
                    
                    # Limitar importe a un rango seguro para evitar overflow numérico en Supabase
                    if abs(importe) > 999999.99:
                        importe = 999999.99 if importe > 0 else -999999.99
                        print(f"⚠️  Importe limitado: {importe} (original: {importe_limpio})")
                except:
                    continue
                
                # Categorizar movimiento
                categoria, tipo_movimiento, tipo_juego = categorizar_movimiento_pokerstars(tipo_str, descripcion, '')
                
                # Generar hash para detección de duplicados
                hash_duplicado = generar_hash_duplicado(
                    fecha, None, tipo_str, descripcion, importe, importe, 'Pokerstars'
                )
                
                # Clasificar nivel de buy-in
                nivel_buyin = clasificar_nivel_buyin(importe) if categoria == 'Torneo' else None
                
                # Crear registro
                registro = {
                    'id': str(uuid.uuid4()),
                    'user_id': str(user_id),
                    'fecha': fecha.isoformat(),
                    'hora': None,
                    'descripcion': descripcion,
                    'importe': round(importe, 2),  # Redondear a 2 decimales
                    'categoria': categoria,
                    'tipo_movimiento': tipo_movimiento,
                    'tipo_juego': tipo_juego,
                    'nivel_buyin': nivel_buyin,
                    'sala': 'Pokerstars',
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
                    
                    # Enviar avance del lote al cliente
                    porcentaje_lote = (resultados_importados / len(registros_sin_duplicados)) * 100
                    progress_callback(f"data: {json.dumps({'tipo': 'lote_completado', 'procesados': resultados_importados, 'total': len(registros_sin_duplicados), 'porcentaje': porcentaje_lote, 'lote_size': len(lote), 'etapa': 'insertando'})}\n\n")
                    
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
        print(f"- Registros en archivo: {total_registros}")
        print(f"- Errores de procesamiento: {errores_procesamiento}")
        print(f"- Duplicados omitidos: {duplicados_encontrados}")
        print(f"- Registros importados: {resultados_importados}")
        
        # Procesamiento posterior a la importación
        print("🔄 Iniciando procesamiento posterior...")
        niveles_reclasificados = reclasificar_niveles_buyin_automatica(user_id)
        tipos_reclasificados = reclasificar_tipos_juego_automatica(user_id)
        print(f"✅ Niveles de buy-in reclasificados: {niveles_reclasificados}")
        print(f"✅ Tipos de juego reclasificados: {tipos_reclasificados}")
        
        return {
            'mensaje': f'Archivo procesado exitosamente. {resultados_importados} registros importados, {duplicados_encontrados} duplicados omitidos.',
            'resultados_importados': resultados_importados,
            'duplicados_encontrados': duplicados_encontrados,
            'duplicados_detalle': duplicados_detalle
        }
        
    except Exception as e:
        return {'error': f'Error procesando archivo Pokerstars: {str(e)}'}

@app.route('/api/importar-progreso', methods=['POST'])
@login_required
def api_importar_progreso():
    """API endpoint para importar archivos con progreso en tiempo real usando SSE"""
    try:
        # El decorador @login_required ya verifica la autenticación
        user_id = current_user.id
        
        if 'archivo' not in request.files:
            return jsonify({'error': 'No se ha seleccionado ningún archivo'}), 400
        
        archivo = request.files['archivo']
        sala = request.form.get('sala', '')
        
        if archivo.filename == '':
            return jsonify({'error': 'No se ha seleccionado ningún archivo'}), 400
        
        if not sala:
            return jsonify({'error': 'Debe seleccionar una sala'}), 400
        
        # Guardar archivo temporalmente
        filename = secure_filename(archivo.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename_with_timestamp = f"{timestamp}_{filename}"
        
        # Crear directorio de uploads si no existe
        upload_folder = 'uploads'
        os.makedirs(upload_folder, exist_ok=True)
        
        filepath = os.path.join(upload_folder, filename_with_timestamp)
        archivo.save(filepath)
        
        def generate_progress():
            try:
                # Función auxiliar para enviar mensajes de progreso
                def progress_callback(msg):
                    # Enviar inmediatamente el mensaje
                    return msg
                
                # Detectar el tipo real del archivo (no solo por extensión)
                with open(filepath, 'rb') as f:
                    primeros_bytes = f.read(100).decode('utf-8', errors='ignore')
                
                es_html_real = primeros_bytes.strip().upper().startswith('<HTML')
                
                # Procesar archivo según la sala y tipo real
                if sala == 'WPN':
                    resultado = procesar_archivo_wpn_con_progreso_streaming(filepath, user_id, progress_callback)
                elif sala == 'Pokerstars':
                    if es_html_real:
                        # Archivo HTML de PokerStars (incluso con extensión Excel)
                        resultado = procesar_archivo_pokerstars_con_progreso_streaming(filepath, user_id, progress_callback)
                    else:
                        # Archivo Excel real de PokerStars
                        resultado = procesar_archivo_pokerstars_excel_con_progreso_streaming(filepath, user_id, progress_callback)
                else:
                    yield f"data: {json.dumps({'error': 'Sala no soportada'})}\n\n"
                    return
                
                # El resultado ya incluye todos los mensajes de progreso
                for msg in resultado:
                    yield msg
                
            except Exception as e:
                yield f"data: {json.dumps({'error': f'Error al procesar el archivo: {str(e)}'})}\n\n"
            finally:
                # Limpiar archivo temporal
                if os.path.exists(filepath):
                    os.remove(filepath)
        
        return Response(
            generate_progress(), 
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Cache-Control'
            }
        )
        
    except Exception as e:
        print(f"Error en API importar progreso: {e}")
        return jsonify({'error': f'Error al procesar el archivo: {str(e)}'}), 500

# API endpoint para verificar el progreso (para futuras implementaciones de WebSocket)
@app.route('/api/previsualizar-archivo', methods=['POST'])
@login_required
def api_previsualizar_archivo():
    """API endpoint para previsualizar el archivo antes de la importación"""
    try:
        if 'archivo' not in request.files:
            return jsonify({'error': 'No se ha seleccionado ningún archivo'}), 400
        
        archivo = request.files['archivo']
        sala = request.form.get('sala', '')
        
        if archivo.filename == '':
            return jsonify({'error': 'No se ha seleccionado ningún archivo'}), 400
        
        if not sala:
            return jsonify({'error': 'Debe seleccionar una sala'}), 400
        
        # Leer el archivo para analizar
        archivo.seek(0)
        contenido_primeros_bytes = archivo.read(100).decode('utf-8', errors='ignore')
        archivo.seek(0)
        
        # Detectar si el archivo es realmente HTML (incluso con extensión Excel)
        es_html = (archivo.filename.lower().endswith('.html') or 
                  contenido_primeros_bytes.strip().upper().startswith('<HTML'))
        
        if es_html:
            # Archivo HTML de Pokerstars (incluso si tiene extensión Excel)
            try:
                content = archivo.read().decode('utf-8')
                soup = BeautifulSoup(content, 'html.parser')
                
                # Contar registros en HTML
                rows = soup.find_all('tr')
                total_registros = len(rows) - 1 if rows else 0  # -1 para excluir header
                
                # Validar que se encontraron registros
                if total_registros == 0:
                    return jsonify({'error': 'No se encontraron registros válidos en el archivo HTML'}), 400
                    
            except UnicodeDecodeError:
                return jsonify({'error': 'Error al leer el archivo HTML. Verifique que el archivo esté en formato UTF-8'}), 400
            except Exception as e:
                return jsonify({'error': f'Error al procesar el archivo HTML: {str(e)}'}), 400
            
        else:
            # Archivo Excel
            try:
                archivo.seek(0)  # Resetear posición del archivo
                
                # Detectar extensión del archivo
                filename = archivo.filename.lower()
                print(f"🔍 Procesando archivo: {filename}")
                
                # Intentar leer con diferentes motores de Excel
                df = None
                error_motores = []
                
                if filename.endswith('.xlsx'):
                    # Para archivos .xlsx, usar openpyxl
                    try:
                        archivo.seek(0)
                        df = pd.read_excel(archivo, engine='openpyxl')
                        print("✅ Archivo leído con openpyxl")
                    except Exception as e:
                        error_motores.append(f"openpyxl: {str(e)}")
                        
                elif filename.endswith('.xls'):
                    # Para archivos .xls, usar xlrd
                    try:
                        archivo.seek(0)
                        df = pd.read_excel(archivo, engine='xlrd')
                        print("✅ Archivo leído con xlrd")
                    except Exception as e:
                        error_motores.append(f"xlrd: {str(e)}")
                
                # Si aún no se pudo leer, intentar todos los motores
                if df is None:
                    for engine_name in ['openpyxl', 'xlrd']:
                        try:
                            archivo.seek(0)
                            df = pd.read_excel(archivo, engine=engine_name)
                            print(f"✅ Archivo leído con {engine_name}")
                            break
                        except Exception as e:
                            error_motores.append(f"{engine_name}: {str(e)}")
                
                # Último recurso: sin especificar motor
                if df is None:
                    try:
                        archivo.seek(0)
                        df = pd.read_excel(archivo)
                        print("✅ Archivo leído con motor por defecto")
                    except Exception as e:
                        error_motores.append(f"default: {str(e)}")
                        raise Exception(f"No se pudo leer el archivo Excel. Errores: {'; '.join(error_motores)}")
                
                total_registros = len(df)
                
                # Filtrar registros sin fecha - manejar diferentes formatos de columna
                columnas_fecha = []
                for col in df.columns:
                    if 'date' in col.lower() or 'fecha' in col.lower():
                        columnas_fecha.append(col)
                
                if columnas_fecha:
                    # Usar la primera columna de fecha encontrada
                    columna_fecha = columnas_fecha[0]
                    df_con_fecha = df.dropna(subset=[columna_fecha])
                    registros_sin_fecha = total_registros - len(df_con_fecha)
                else:
                    # Si no hay columna de fecha, asumir que todos son válidos
                    df_con_fecha = df
                    registros_sin_fecha = 0
                
                return jsonify({
                    'total_registros': total_registros,
                    'registros_validos': len(df_con_fecha),
                    'registros_sin_fecha': registros_sin_fecha,
                    'sala': sala,
                    'nombre_archivo': archivo.filename,
                    'tipo_archivo': 'Excel',
                    'columnas_detectadas': list(df.columns) if hasattr(df, 'columns') else []
                })
            except Exception as e:
                return jsonify({'error': f'Error al procesar el archivo Excel: {str(e)}'}), 400
        
        return jsonify({
            'total_registros': total_registros,
            'registros_validos': total_registros,
            'registros_sin_fecha': 0,
            'sala': sala,
            'nombre_archivo': archivo.filename,
            'tipo_archivo': 'HTML',
            'columnas_detectadas': ['Fecha', 'Tipo', 'Descripción', 'Importe']
        })
        
    except Exception as e:
        return jsonify({'error': f'Error al analizar el archivo: {str(e)}'}), 500

@app.route('/api/progreso')
@login_required
def api_progreso():
    """API endpoint para obtener el progreso de importación"""
    # Por ahora retornamos un estado básico
    return jsonify({
        'estado': 'procesando',
        'mensaje': 'Procesando archivo...'
    })

# API endpoints para informes
@app.route('/api/informes/opciones')
def api_informes_opciones():
    """API endpoint para obtener opciones de informes"""
    try:
        # Usar usuario admin por defecto si no hay sesión
        if current_user.is_authenticated:
            user_id = str(current_user.id)
            print(f"🔍 Usuario autenticado: {user_id}")
        else:
            user_id = "00000000-0000-0000-0000-000000000001"  # Usuario admin por defecto
            print(f"🔍 Usando usuario por defecto: {user_id}")
        
        # Obtener opciones únicas usando consultas específicas para evitar cargar todos los registros
        # Obtener salas únicas - versión optimizada
        try:
            salas = obtener_valores_unicos_optimizado('poker_results', 'sala', user_id)
            print(f"🔍 Salas encontradas: {salas}")
        except Exception as e:
            print(f"❌ Error obteniendo salas: {e}")
            salas = []
        
        # Obtener categorías únicas - versión optimizada
        try:
            categorias = obtener_valores_unicos_optimizado('poker_results', 'categoria', user_id)
        except Exception as e:
            print(f"❌ Error obteniendo categorías: {e}")
            categorias = []
        
        # Obtener tipos de juego únicos - versión optimizada
        try:
            tipos_juego = obtener_valores_unicos_optimizado('poker_results', 'tipo_juego', user_id)
        except Exception as e:
            print(f"❌ Error obteniendo tipos de juego: {e}")
            tipos_juego = []
        
        # Obtener niveles de buy-in únicos - versión optimizada
        try:
            niveles_buyin = obtener_valores_unicos_optimizado('poker_results', 'nivel_buyin', user_id)
        except Exception as e:
            print(f"❌ Error obteniendo niveles de buy-in: {e}")
            niveles_buyin = []
        
        # Obtener tipos de movimiento únicos - versión optimizada
        try:
            tipos_movimiento = obtener_valores_unicos_optimizado('poker_results', 'tipo_movimiento', user_id)
        except Exception as e:
            print(f"❌ Error obteniendo tipos de movimiento: {e}")
            tipos_movimiento = []
        
        # Obtener rangos de fechas
        try:
            fechas_result = supabase.table('poker_results').select('fecha').eq('user_id', user_id).range(0, 20000).execute()
            fechas = [record['fecha'] for record in fechas_result.data if record.get('fecha')]
            fecha_min = min(fechas) if fechas else None
            fecha_max = max(fechas) if fechas else None
        except Exception as e:
            print(f"❌ Error obteniendo fechas: {e}")
            fecha_min = None
            fecha_max = None
        
        return jsonify({
            'success': True,
            'opciones': {
                'salas': salas,
                'categorias': categorias,
                'tipos_juego': tipos_juego,
                'niveles_buyin': niveles_buyin,
                'tipos_movimiento': tipos_movimiento,
                'fecha_min': fecha_min,
                'fecha_max': fecha_max
            }
        })
    except Exception as e:
        print(f"Error en API opciones informes: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/informes/resultados')
def api_informes_resultados():
    """API endpoint para obtener resultados de informes"""
    try:
        # Usar usuario admin por defecto si no hay sesión
        if current_user.is_authenticated:
            user_id = str(current_user.id)
        else:
            user_id = "00000000-0000-0000-0000-000000000001"  # Usuario admin por defecto
        
        # Obtener parámetros de filtro (soporte para arrays y valores únicos)
        salas = request.args.getlist('salas[]') or [request.args.get('sala', '')]
        salas = [s for s in salas if s]  # Filtrar valores vacíos
        
        categorias = request.args.getlist('categorias[]') or [request.args.get('categoria', '')]
        categorias = [c for c in categorias if c]  # Filtrar valores vacíos
        
        tipos_juego = request.args.getlist('tipos_juego[]') or [request.args.get('tipo_juego', '')]
        tipos_juego = [t for t in tipos_juego if t]  # Filtrar valores vacíos
        
        niveles_buyin = request.args.getlist('niveles_buyin[]') or [request.args.get('nivel_buyin', '')]
        niveles_buyin = [n for n in niveles_buyin if n]  # Filtrar valores vacíos
        
        fecha_inicio = request.args.get('fecha_inicio', '')
        fecha_fin = request.args.get('fecha_fin', '')
        
        tipos_movimiento = request.args.getlist('tipos_movimiento[]') or [request.args.get('tipo_movimiento', '')]
        tipos_movimiento = [t for t in tipos_movimiento if t]  # Filtrar valores vacíos
        
        # Parámetros de paginación y búsqueda
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))  # Reducido a 50 registros por página
        offset = (page - 1) * per_page
        
        # Parámetro de búsqueda
        busqueda = request.args.get('busqueda', '').strip()
        
        # Construir consulta base
        query = supabase.table('poker_results').select('*').eq('user_id', user_id)
        
        # Aplicar filtros
        if salas:
            query = query.in_('sala', salas)
        if categorias:
            query = query.in_('categoria', categorias)
        if tipos_juego:
            query = query.in_('tipo_juego', tipos_juego)
        if niveles_buyin:
            query = query.in_('nivel_buyin', niveles_buyin)
        if tipos_movimiento:
            query = query.in_('tipo_movimiento', tipos_movimiento)
        if fecha_inicio:
            query = query.gte('fecha', fecha_inicio)
        if fecha_fin:
            query = query.lte('fecha', fecha_fin)
        
        # Aplicar búsqueda si se proporciona
        if busqueda:
            # Buscar en descripción, sala, tipo_movimiento, categoria
            # Usar ilike para búsqueda case-insensitive
            query = query.or_(f'descripcion.ilike.%{busqueda}%,sala.ilike.%{busqueda}%,tipo_movimiento.ilike.%{busqueda}%,categoria.ilike.%{busqueda}%')
        
        # Obtener total de registros para estadísticas
        def obtener_conteo():
            count_query = supabase.table('poker_results').select('id', count='exact').eq('user_id', user_id)
            
            # Aplicar los mismos filtros para el conteo
            if salas:
                count_query = count_query.in_('sala', salas)
            if categorias:
                count_query = count_query.in_('categoria', categorias)
            if tipos_juego:
                count_query = count_query.in_('tipo_juego', tipos_juego)
            if niveles_buyin:
                count_query = count_query.in_('nivel_buyin', niveles_buyin)
            if tipos_movimiento:
                count_query = count_query.in_('tipo_movimiento', tipos_movimiento)
            if fecha_inicio:
                count_query = count_query.gte('fecha', fecha_inicio)
            if fecha_fin:
                count_query = count_query.lte('fecha', fecha_fin)
            if busqueda:
                count_query = count_query.or_(f'descripcion.ilike.%{busqueda}%,sala.ilike.%{busqueda}%,tipo_movimiento.ilike.%{busqueda}%,categoria.ilike.%{busqueda}%')
            
            return count_query.execute()
        
        count_result = ejecutar_con_reintentos(obtener_conteo)
        total_registros = count_result.count if hasattr(count_result, 'count') else 0
        
        # Aplicar paginación y ordenamiento
        query = query.order('fecha', desc=True).order('id', desc=True)
        query = query.range(offset, offset + per_page - 1)
        
        # Ejecutar consulta con reintentos
        def obtener_datos():
            return query.execute()
        
        result = ejecutar_con_reintentos(obtener_datos)
        records = result.data if result.data else []
        
        # Para estadísticas, usar una estrategia más eficiente y resistente a errores
        print(f"🔄 Calculando estadísticas (usuario: {user_id})")
        
        # Inicializar estadísticas por defecto
        torneos_jugados = 0
        total_invertido = 0.0
        total_ganancias = 0.0
        total_importe = 0.0
        roi = 0.0
        por_categoria = {}
        
        try:
            # Obtener todos los registros del usuario para estadísticas (aplicando filtros)
            def obtener_estadisticas_torneos():
                query = supabase.table('poker_results').select('importe, categoria, tipo_movimiento').eq('user_id', user_id)
                if categorias:
                    query = query.in_('categoria', categorias)
                if salas:
                    query = query.in_('sala', salas)
                if fecha_inicio:
                    query = query.gte('fecha', fecha_inicio)
                if fecha_fin:
                    query = query.lte('fecha', fecha_fin)
                return query.range(0, 20000).execute()  # Obtener hasta 20k registros
            
            stats_result = ejecutar_con_reintentos(obtener_estadisticas_torneos)
            if stats_result.data:
                all_records = stats_result.data
                print(f"📊 Registros obtenidos para estadísticas: {len(all_records)}")
                
                # Calcular estadísticas usando la lógica correcta de SQLite
                # 1. Torneos jugados: solo Buy In + Torneo
                torneos_jugados = len([r for r in all_records 
                                     if r.get('tipo_movimiento') == 'Buy In' and r.get('categoria') == 'Torneo'])
                
                # 2. Filtrar solo registros de torneos para cálculos específicos
                torneos = [r for r in all_records if r.get('categoria') == 'Torneo']
                
                # 3. Total invertido: solo egresos (importes negativos) de torneos
                total_invertido = sum([abs(float(record.get('importe', 0))) 
                                     for record in torneos if float(record.get('importe', 0)) < 0])
                
                # 4. Total ganancias: solo ingresos (importes positivos) de torneos
                total_ganancias = sum([float(record.get('importe', 0)) 
                                     for record in torneos if float(record.get('importe', 0)) > 0])
                
                # 5. Calcular ROI: (ganancias - invertido) / invertido * 100
                roi = 0
                if total_invertido > 0:
                    roi = ((total_ganancias - total_invertido) / total_invertido) * 100
                
                # 6. Suma total de todos los importes (incluyendo todos los registros filtrados)
                total_importe = sum([float(record.get('importe', 0)) for record in all_records])
                
                # 7. Resultado económico excluyendo transferencias, retiros y depósitos
                movimientos_poker = [r for r in all_records 
                                   if r.get('categoria') not in ['Transferencia', 'Depósito', 'Retiro'] 
                                   and r.get('tipo_movimiento') not in ['Retiro']]
                resultado_economico = sum([float(record.get('importe', 0)) for record in movimientos_poker])
                
                # Agrupar por categoría
                for record in all_records:
                    cat = record.get('categoria', 'Sin categoría')
                    if cat not in por_categoria:
                        por_categoria[cat] = {'count': 0, 'total': 0}
                    por_categoria[cat]['count'] += 1
                    por_categoria[cat]['total'] += float(record.get('importe', 0))
        
                print(f"🎯 Estadísticas calculadas (lógica SQLite):")
                print(f"   - Torneos jugados (Buy In + Torneo): {torneos_jugados}")
                print(f"   - Total invertido (egresos torneos): ${total_invertido:.2f}")
                print(f"   - Total ganancias (ingresos torneos): ${total_ganancias:.2f}")
                print(f"   - Balance total (todos registros): ${total_importe:.2f}")
                print(f"   - ROI: {roi:.1f}%")
                print(f"   - Resultado económico (sin transferencias): ${resultado_economico:.2f}")
            else:
                print("⚠️  No se pudieron obtener registros para estadísticas")
                
        except Exception as e:
            print(f"⚠️  Error calculando estadísticas: {e}")
            # Usar valores por defecto si hay error
        
        # Calcular información de paginación
        total_pages = (total_registros + per_page - 1) // per_page
        has_next = page < total_pages
        has_prev = page > 1
        
        # Debug: mostrar estadísticas que se van a enviar
        print(f"📤 Enviando estadísticas al frontend:")
        print(f"   - torneos_jugados: {torneos_jugados}")
        print(f"   - total_invertido: {total_invertido}")
        print(f"   - total_ganancias: {total_ganancias}")
        print(f"   - roi: {roi}")
        print(f"   - resultado_economico: {resultado_economico}")
        
        response_data = {
            'success': True,
            'resultados': {
                'total_registros': total_registros,
                'total_importe': total_importe,
                'torneos_jugados': torneos_jugados,
                'total_invertido': total_invertido,
                'total_ganancias': total_ganancias,
                'roi': roi,
                'resultado_economico': resultado_economico,
                'por_categoria': por_categoria,
                'registros': records,
                'paginacion': {
                    'page': page,
                    'per_page': per_page,
                    'total_pages': total_pages,
                    'has_next': has_next,
                    'has_prev': has_prev
                },
                'busqueda': {
                    'termino': busqueda,
                    'activa': bool(busqueda)
                }
            }
        }
        
        # Calcular resultados diarios de los últimos 10 días (SIN FILTROS, desde fecha actual)
        from datetime import timedelta
        hoy = datetime.now().date()
        ultimos_10_dias = [hoy - timedelta(days=i) for i in range(10)]
        ultimos_10_dias.reverse()
        
        # Obtener TODOS los movimientos de poker del usuario (sin filtros) para el gráfico
        todos_movimientos_poker = supabase.table('poker_results').select('*').eq('user_id', user_id).neq('categoria', 'Transferencia').neq('categoria', 'Depósito').neq('tipo_movimiento', 'Retiro').execute()
        
        resultados_diarios = []
        for fecha in ultimos_10_dias:
            # Filtrar movimientos de poker para esta fecha específica
            movimientos_dia = [r for r in todos_movimientos_poker.data if r['fecha'] == fecha.isoformat()]
            resultado_dia = sum(float(r['importe']) for r in movimientos_dia)
            resultados_diarios.append({
                'fecha': fecha.isoformat(),
                'resultado': resultado_dia,
                'movimientos': len(movimientos_dia)
            })
        
        # Agregar resultados_diarios a la respuesta
        response_data['resultados']['resultados_diarios'] = resultados_diarios
        
        print(f"📤 JSON completo a enviar: {response_data}")
        return jsonify(response_data)
    except Exception as e:
        print(f"❌ Error crítico en API resultados informes: {e}")
        import traceback
        traceback.print_exc()
        
        # Determinar el tipo de error para respuesta más específica
        error_msg = str(e)
        if "Resource temporarily unavailable" in error_msg or "ReadError" in error_msg:
            error_msg = "Error de conexión temporal con la base de datos. Intenta nuevamente en unos momentos."
        elif "TimeoutException" in error_msg:
            error_msg = "Tiempo de espera agotado. La consulta es muy compleja, intenta filtrar más los datos."
        else:
            error_msg = f"Error interno: {error_msg}"
        
        return jsonify({
            'success': False, 
            'error': error_msg,
            'resultados': {
                'total_registros': 0,
                'total_importe': 0.0,
                'torneos_jugados': 0,
                'total_invertido': 0.0,
                'total_ganancias': 0.0,
                'roi': 0.0,
                'resultado_economico': 0.0,
                'por_categoria': {},
                'registros': [],
                'paginacion': {
                    'page': int(request.args.get('page', 1)),
                    'per_page': int(request.args.get('per_page', 50)),
                    'total_pages': 0,
                    'has_next': False,
                    'has_prev': False
                },
                'busqueda': {
                    'termino': request.args.get('busqueda', ''),
                    'activa': bool(request.args.get('busqueda', ''))
                }
            }
        }), 500

@app.route('/favicon.ico')
def favicon():
    """Servir el favicon"""
    return send_from_directory(os.path.join(app.root_path, 'static'),
                              'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/api/eliminar-todos', methods=['POST'])
@login_required
def api_eliminar_todos():
    """Elimina todos los registros del usuario actual"""
    try:
        # Contar registros del usuario antes de eliminar
        result = supabase.table('poker_results').select('id', count='exact').eq('user_id', current_user.id).execute()
        total_registros = result.count if result.count else 0
        
        if total_registros == 0:
            return jsonify({
                'mensaje': 'No se encontraron registros para eliminar',
                'registros_eliminados': 0
            })
        
        # Eliminar todos los registros del usuario
        supabase.table('poker_results').delete().eq('user_id', current_user.id).execute()
        
        return jsonify({
            'mensaje': f'Se eliminaron {total_registros} registros exitosamente',
            'registros_eliminados': total_registros
        })
        
    except Exception as e:
        return jsonify({'error': f'Error al eliminar registros: {str(e)}'}), 500

@app.route('/api/eliminar-por-sala', methods=['POST'])
@login_required
def api_eliminar_por_sala():
    """Elimina registros de una sala específica del usuario actual"""
    try:
        data = request.get_json()
        sala = data.get('sala')
        
        if not sala:
            return jsonify({'error': 'Sala no especificada'}), 400
        
        # Contar registros de la sala del usuario antes de eliminar
        result = supabase.table('poker_results').select('id', count='exact').eq('user_id', current_user.id).eq('sala', sala).execute()
        registros_sala = result.count if result.count else 0
        
        if registros_sala == 0:
            return jsonify({
                'mensaje': f'No se encontraron registros de la sala {sala}',
                'registros_eliminados': 0
            })
        
        # Eliminar registros de la sala del usuario
        supabase.table('poker_results').delete().eq('user_id', current_user.id).eq('sala', sala).execute()
        
        return jsonify({
            'mensaje': f'Se eliminaron {registros_sala} registros de la sala {sala}',
            'registros_eliminados': registros_sala,
            'sala': sala
        })
        
    except Exception as e:
        return jsonify({'error': f'Error al eliminar registros de la sala: {str(e)}'}), 500

@app.route('/api/salas-optimizado', methods=['GET'])
def api_salas_optimizado():
    """Endpoint optimizado que devuelve solo un registro por sala para filtros"""
    try:
        # Usar usuario admin por defecto si no hay sesión
        if current_user.is_authenticated:
            user_id = str(current_user.id)
            print(f"🔍 Usuario autenticado: {user_id}")
        else:
            user_id = "00000000-0000-0000-0000-000000000001"  # Usuario admin por defecto
            print(f"🔍 Usando usuario por defecto: {user_id}")
        
        # Usar consulta optimizada para obtener salas únicas
        salas_unicas = obtener_valores_unicos_optimizado('poker_results', 'sala', user_id)
        
        # Ahora obtenemos un registro de ejemplo para cada sala
        salas_con_info = []
        for sala in salas_unicas:
            try:
                # Obtener un registro de ejemplo de cada sala con reintentos
                def obtener_ejemplo_sala():
                    return supabase.table('poker_results').select('*').eq('user_id', user_id).eq('sala', sala).limit(1).execute()
                
                ejemplo = ejecutar_con_reintentos(obtener_ejemplo_sala)
                if ejemplo.data:
                    salas_con_info.append({
                        'sala': sala,
                        'fecha_ejemplo': ejemplo.data[0].get('fecha'),
                        'descripcion_ejemplo': ejemplo.data[0].get('descripcion', '')[:50] + '...' if ejemplo.data[0].get('descripcion') else '',
                        'categoria_ejemplo': ejemplo.data[0].get('categoria')
                    })
            except Exception as e:
                print(f"⚠️  Error obteniendo ejemplo para sala {sala}: {e}")
                # Si falla obtener el ejemplo, agregar solo el nombre de la sala
                salas_con_info.append({
                    'sala': sala,
                    'fecha_ejemplo': None,
                    'descripcion_ejemplo': '',
                    'categoria_ejemplo': None
                })
        
        print(f"✅ Salas encontradas: {[s['sala'] for s in salas_con_info]}")
        
        return jsonify({
            'success': True,
            'salas': salas_con_info
        })
        
    except Exception as e:
        print(f"❌ Error obteniendo salas optimizadas: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/migrar-registros-admin', methods=['POST'])
@login_required
def api_migrar_registros_admin():
    """Migrar todos los registros al usuario admin actual"""
    try:
        if not current_user.is_admin:
            return jsonify({'error': 'Solo administradores pueden ejecutar esta acción'}), 403
        
        current_admin_id = str(current_user.id)
        print(f"🔄 Migrando registros al admin: {current_admin_id}")
        
        # Obtener todos los registros que no pertenecen al admin actual
        all_records = supabase.table('poker_results').select('*').neq('user_id', current_admin_id).execute()
        records_to_migrate = all_records.data if all_records.data else []
        
        print(f"📊 Encontrados {len(records_to_migrate)} registros para migrar")
        
        if not records_to_migrate:
            return jsonify({
                'success': True,
                'message': 'No hay registros para migrar',
                'migrated_count': 0
            })
        
        # Migrar en lotes de 1000 registros
        migrated_count = 0
        batch_size = 1000
        
        for i in range(0, len(records_to_migrate), batch_size):
            batch = records_to_migrate[i:i + batch_size]
            
            # Actualizar user_id para este lote
            record_ids = [record['id'] for record in batch]
            
            for record_id in record_ids:
                try:
                    supabase.table('poker_results').update({
                        'user_id': current_admin_id
                    }).eq('id', record_id).execute()
                    migrated_count += 1
                except Exception as e:
                    print(f"❌ Error migrando registro {record_id}: {e}")
                    continue
            
            print(f"✅ Migrado lote {i//batch_size + 1}: {len(batch)} registros")
        
        print(f"✅ Migración completada: {migrated_count} registros migrados")
        
        return jsonify({
            'success': True,
            'message': f'Se migraron {migrated_count} registros al usuario admin',
            'migrated_count': migrated_count
        })
        
    except Exception as e:
        print(f"❌ Error en migración: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/debug-consulta-salas', methods=['GET'])
@login_required
def api_debug_consulta_salas():
    """Endpoint temporal para debug específico de consulta de salas"""
    try:
        user_id = str(current_user.id)
        print(f"🔍 Debug consulta salas - Usuario: {user_id}")
        
        # Consulta directa igual que en /api/informes/opciones
        print("🔍 Ejecutando consulta: supabase.table('poker_results').select('sala').eq('user_id', user_id).range(0, 20000)")
        salas_result = supabase.table('poker_results').select('sala').eq('user_id', user_id).range(0, 20000).execute()
        
        print(f"🔍 Resultado raw: {len(salas_result.data)} registros")
        print(f"🔍 Primeros 10 registros: {salas_result.data[:10]}")
        
        # Obtener todas las salas únicas
        todas_las_salas = [record['sala'] for record in salas_result.data if record.get('sala')]
        salas_unicas = list(set(todas_las_salas))
        
        print(f"🔍 Total registros con sala: {len(todas_las_salas)}")
        print(f"🔍 Salas únicas encontradas: {salas_unicas}")
        
        # Contar por sala
        conteo_salas = {}
        for sala in todas_las_salas:
            conteo_salas[sala] = conteo_salas.get(sala, 0) + 1
        
        print(f"🔍 Conteo por sala: {conteo_salas}")
        
        return jsonify({
            'success': True,
            'user_id': user_id,
            'total_registros': len(salas_result.data),
            'registros_con_sala': len(todas_las_salas),
            'salas_unicas': salas_unicas,
            'conteo_por_sala': conteo_salas,
            'primeros_10': salas_result.data[:10]
        })
        
    except Exception as e:
        print(f"❌ Error en debug consulta salas: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug-usuarios', methods=['GET'])
@login_required
def api_debug_usuarios():
    """Endpoint temporal para debug de usuarios"""
    try:
        # Obtener todos los usuarios
        users_result = supabase.table('users').select('*').execute()
        users = users_result.data if users_result.data else []
        
        # Obtener registros con sus user_ids
        records_result = supabase.table('poker_results').select('user_id, sala').execute()
        records = records_result.data if records_result.data else []
        
        # Agrupar por user_id
        user_records = {}
        for record in records:
            user_id = record.get('user_id')
            sala = record.get('sala')
            if user_id not in user_records:
                user_records[user_id] = {}
            if sala not in user_records[user_id]:
                user_records[user_id][sala] = 0
            user_records[user_id][sala] += 1
        
        return jsonify({
            'current_user': {
                'id': str(current_user.id),
                'username': current_user.username,
                'email': current_user.email
            },
            'all_users': users,
            'records_by_user': user_records
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug-salas', methods=['GET'])
@login_required
def api_debug_salas():
    """Endpoint temporal para debug de salas"""
    try:
        user_id = str(current_user.id)
        print(f"🔍 Debug - Usuario: {user_id}")
        
        # Consulta directa para ver todas las salas
        result = supabase.table('poker_results').select('sala, user_id, fecha, descripcion').range(0, 20000).execute()
        print(f"🔍 Debug - Todos los registros: {len(result.data)}")
        
        # Analizar user_ids únicos
        user_ids_unicos = list(set([str(r.get('user_id')) for r in result.data]))
        print(f"🔍 Debug - User IDs únicos en BD: {user_ids_unicos}")
        
        # Analizar salas únicas
        salas_unicas = list(set([r['sala'] for r in result.data if r.get('sala')]))
        print(f"🔍 Debug - Salas únicas en BD: {salas_unicas}")
        
        # Contar registros por sala
        for sala in salas_unicas:
            registros_sala = [r for r in result.data if r.get('sala') == sala]
            user_ids_sala = list(set([str(r.get('user_id')) for r in registros_sala]))
            print(f"🔍 Debug - Sala '{sala}': {len(registros_sala)} registros, User IDs: {user_ids_sala}")
        
        # Filtrar por usuario
        user_records = [r for r in result.data if str(r.get('user_id')) == user_id]
        print(f"🔍 Debug - Registros del usuario: {len(user_records)}")
        
        # Obtener salas únicas del usuario
        user_salas = list(set([r['sala'] for r in user_records if r.get('sala')]))
        print(f"🔍 Debug - Salas del usuario: {user_salas}")
        
        return jsonify({
            'user_id': user_id,
            'total_records': len(result.data),
            'user_records': len(user_records),
            'user_salas': user_salas,
            'sample_records': user_records[:5]  # Primeros 5 registros
        })
    except Exception as e:
        print(f"❌ Debug error: {e}")
        return jsonify({'error': str(e)}), 500




@app.route('/api/salas-disponibles', methods=['GET'])
@login_required
def api_salas_disponibles():
    """Obtiene las salas disponibles del usuario actual"""
    try:
        user_id = str(current_user.id)
        print(f"🔍 API Salas Disponibles - Usuario: {user_id}")
        
        # Obtener salas únicas del usuario usando la función optimizada
        salas = obtener_valores_unicos_optimizado('poker_results', 'sala', user_id)
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
            'salas': salas_info
        })
        
    except Exception as e:
        return jsonify({'error': f'Error al obtener salas: {str(e)}'}), 500

@app.route('/api/test-supabase', methods=['GET'])
def api_test_supabase():
    """Endpoint de prueba para verificar conectividad con Supabase"""
    try:
        # Probar consulta simple a la tabla users
        response = supabase.table('users').select('id, username, email').limit(5).execute()
        users = response.data if response.data else []
        
        return jsonify({
            'success': True,
            'message': 'Conexión con Supabase exitosa',
            'users_found': len(users),
            'users': users
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error conectando con Supabase: {str(e)}'
        }), 500

@app.route('/api/create-admin', methods=['POST'])
def api_create_admin():
    """Endpoint para crear usuario admin si no existe"""
    try:
        # Verificar si ya existe un usuario admin
        response = supabase.table('users').select('*').eq('username', 'admin').execute()
        
        if response.data:
            return jsonify({
                'success': True,
                'message': 'Usuario admin ya existe',
                'user': response.data[0]
            })
        
        # Crear usuario admin
        admin_password_hash = generate_password_hash('admin')
        new_admin = {
            'id': '00000000-0000-0000-0000-000000000001',
            'username': 'admin',
            'email': 'admin@pokerresults.com',
            'password_hash': admin_password_hash,
            'is_admin': True,
            'is_active': True,
            'created_at': datetime.now().isoformat()
        }
        
        result = supabase.table('users').insert(new_admin).execute()
        
        return jsonify({
            'success': True,
            'message': 'Usuario admin creado exitosamente',
            'user': result.data[0] if result.data else new_admin
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error creando usuario admin: {str(e)}'
        }), 500

@app.route('/api/debug-estadisticas', methods=['GET'])
@login_required
def api_debug_estadisticas():
    """Endpoint temporal para debug de estadísticas"""
    try:
        user_id = str(current_user.id)
        print(f"🔍 DEBUG ESTADÍSTICAS - Usuario: {user_id}")
        
        # Obtener todos los registros del usuario
        all_user_records = obtener_registros_completos_supabase('poker_results', '*', user_id)
        print(f"📊 Total registros del usuario: {len(all_user_records)}")
        
        # Calcular estadísticas específicas
        torneos_jugados = len([r for r in all_user_records if r.get('categoria') == 'Torneo'])
        total_invertido = sum([abs(float(record.get('importe', 0))) for record in all_user_records if float(record.get('importe', 0)) < 0])
        total_ganancias = sum([float(record.get('importe', 0)) for record in all_user_records if float(record.get('importe', 0)) > 0])
        total_importe = sum([float(record.get('importe', 0)) for record in all_user_records])
        
        roi = 0.0
        if total_invertido > 0:
            roi = ((total_ganancias - total_invertido) / total_invertido) * 100
        
        estadisticas = {
            'torneos_jugados': torneos_jugados,
            'total_invertido': total_invertido,
            'total_ganancias': total_ganancias,
            'total_importe': total_importe,
            'roi': roi,
            'resultado_economico': total_ganancias - total_invertido,
            'total_registros': len(all_user_records)
        }
        
        print(f"🎯 Estadísticas calculadas: {estadisticas}")
        
        return jsonify({
            'success': True,
            'estadisticas': estadisticas,
            'debug_info': {
                'total_registros_procesados': len(all_user_records),
                'usuario': user_id
            }
        })
        
    except Exception as e:
        print(f"❌ Error en debug estadísticas: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analisis/insights', methods=['GET'])
def api_analisis_insights():
    """Análisis avanzado con insights para gestión del juego"""
    try:
        # Usar usuario admin por defecto si no hay sesión
        if current_user.is_authenticated:
            user_id = str(current_user.id)
        else:
            user_id = "00000000-0000-0000-0000-000000000001"  # Usuario admin por defecto
        
        # Obtener todos los registros de torneos del usuario
        result = supabase.table('poker_results').select('*').eq('user_id', user_id).eq('categoria', 'Torneo').execute()
        torneos = result.data
        
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
        if torneo.get('nivel_buyin'):
            nivel = torneo['nivel_buyin']
            if nivel not in buyin_stats:
                buyin_stats[nivel] = {
                    'total_torneos': 0,
                    'total_invertido': 0,
                    'total_ganancias': 0,
                    'roi': 0,
                    'mejor_racha': 0,
                    'peor_racha': 0,
                    'racha_actual': 0,
                    'salas': set()
                }
            
            buyin_stats[nivel]['total_torneos'] += 1
            importe = float(torneo.get('importe', 0))
            buyin_stats[nivel]['total_invertido'] += abs(importe) if importe < 0 else 0
            buyin_stats[nivel]['total_ganancias'] += importe if importe > 0 else 0
            buyin_stats[nivel]['salas'].add(torneo.get('sala', ''))
    
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
        sala = torneo.get('sala')
        if sala:
            if sala not in sala_stats:
                sala_stats[sala] = {
                    'total_torneos': 0,
                    'total_invertido': 0,
                    'total_ganancias': 0,
                    'roi': 0,
                    'torneos_ganados': 0,
                    'tipos_juego': set(),
                    'niveles_buyin': set()
                }
            
            importe = float(torneo.get('importe', 0))
            sala_stats[sala]['total_torneos'] += 1
            sala_stats[sala]['total_invertido'] += abs(importe) if importe < 0 else 0
            sala_stats[sala]['total_ganancias'] += importe if importe > 0 else 0
            
            if importe > 0:
                sala_stats[sala]['torneos_ganados'] += 1
            
            if torneo.get('tipo_juego'):
                sala_stats[sala]['tipos_juego'].add(torneo['tipo_juego'])
            
            if torneo.get('nivel_buyin'):
                sala_stats[sala]['niveles_buyin'].add(torneo['nivel_buyin'])
    
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
    from datetime import datetime
    
    # Agrupar por día de la semana
    dias_semana = defaultdict(lambda: {'torneos': 0, 'resultado': 0})
    dias_nombres = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    
    # Agrupar por hora del día
    horas_dia = defaultdict(lambda: {'torneos': 0, 'resultado': 0})
    
    for torneo in torneos:
        fecha_str = torneo.get('fecha')
        if fecha_str:
            try:
                fecha = datetime.fromisoformat(fecha_str).date()
                dia_semana = fecha.weekday()
                importe = float(torneo.get('importe', 0))
                
                dias_semana[dia_semana]['torneos'] += 1
                dias_semana[dia_semana]['resultado'] += importe
                
                hora_str = torneo.get('hora')
                if hora_str:
                    try:
                        hora = datetime.fromisoformat(f"2000-01-01T{hora_str}").hour
                        horas_dia[hora]['torneos'] += 1
                        horas_dia[hora]['resultado'] += importe
                    except:
                        pass
            except:
                pass
    
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
        tipo_juego = torneo.get('tipo_juego')
        if tipo_juego:
            if tipo_juego not in juego_stats:
                juego_stats[tipo_juego] = {
                    'total_torneos': 0,
                    'total_invertido': 0,
                    'total_ganancias': 0,
                    'roi': 0,
                    'torneos_ganados': 0
                }
            
            importe = float(torneo.get('importe', 0))
            juego_stats[tipo_juego]['total_torneos'] += 1
            juego_stats[tipo_juego]['total_invertido'] += abs(importe) if importe < 0 else 0
            juego_stats[tipo_juego]['total_ganancias'] += importe if importe > 0 else 0
            
            if importe > 0:
                juego_stats[tipo_juego]['torneos_ganados'] += 1
    
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
    from datetime import datetime
    
    resultados_diarios = defaultdict(float)
    
    for torneo in torneos:
        fecha_str = torneo.get('fecha')
        if fecha_str:
            try:
                fecha = datetime.fromisoformat(fecha_str).date()
                importe = float(torneo.get('importe', 0))
                resultados_diarios[fecha] += importe
            except:
                pass
    
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

# =============================================================================
# FUNCIONES AUXILIARES PARA SWAGGER
# =============================================================================

def require_auth_or_session(f):
    """Decorador que permite autenticación por token o sesión"""
    def decorated_function(*args, **kwargs):
        # Verificar si hay token en el header Authorization
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            # Para simplificar, asumimos que cualquier token válido es del usuario admin
            # En producción, deberías validar el token contra la base de datos
            if token:
                # Crear un usuario temporal para la API
                user = User(
                    id="00000000-0000-0000-0000-000000000001",
                    username="admin",
                    email="admin@example.com",
                    is_admin=True
                )
                # Establecer como usuario actual
                from flask_login import login_user
                login_user(user)
                return f(*args, **kwargs)
        
        # Si no hay token, verificar sesión normal
        if not current_user.is_authenticated:
            return {'error': 'No autenticado'}, 401
        
        return f(*args, **kwargs)
    
    decorated_function.__name__ = f.__name__
    return decorated_function

# =============================================================================
# ENDPOINTS DE SWAGGER
# =============================================================================

@auth_ns.route('/login')
class Login(Resource):
    @api.doc('login_user')
    @api.expect(login_model)
    @api.response(200, 'Login exitoso')
    @api.response(401, 'Credenciales inválidas', error_model)
    def post(self):
        """Iniciar sesión de usuario y obtener token"""
        args = request.get_json() or {}
        username = args.get('username')
        password = args.get('password')
        
        if not username or not password:
            return {'error': 'Username y password son requeridos'}, 400
        
        try:
            # Buscar usuario en Supabase
            response = supabase.table('users').select('*').eq('username', username).execute()
            
            if not response.data:
                return {'error': 'Credenciales inválidas'}, 401
            
            user_data = response.data[0]
            
            # Verificar contraseña
            if not check_password_hash(user_data['password_hash'], password):
                return {'error': 'Credenciales inválidas'}, 401
            
            # Crear sesión
            user = User(
                id=user_data['id'],
                username=user_data['username'],
                email=user_data['email'],
                is_admin=user_data.get('is_admin', False),
                is_active=user_data.get('is_active', True)
            )
            login_user(user)
            
            # Generar un token simple para la sesión
            import secrets
            token = secrets.token_urlsafe(32)
            session['api_token'] = token
            
            return {
                'mensaje': 'Login exitoso',
                'token': token,
                'user_id': user_data['id'],
                'username': user_data['username']
            }, 200
            
        except Exception as e:
            return {'error': f'Error en login: {str(e)}'}, 500

@auth_ns.route('/token')
class GetToken(Resource):
    @api.doc('get_current_token')
    @api.response(200, 'Token obtenido exitosamente')
    @api.response(401, 'No autenticado', error_model)
    @login_required
    def get(self):
        """Obtener token de autenticación actual"""
        token = session.get('api_token')
        if token:
            return {
                'token': token,
                'user_id': current_user.id,
                'username': current_user.username
            }, 200
        else:
            return {'error': 'No hay token de sesión activo'}, 401

@auth_ns.route('/logout')
class Logout(Resource):
    @api.doc('logout_user')
    @api.response(200, 'Logout exitoso')
    @login_required
    def post(self):
        """Cerrar sesión de usuario"""
        session.pop('api_token', None)
        logout_user()
        return {'mensaje': 'Logout exitoso'}, 200

@import_ns.route('/upload')
class ImportUpload(Resource):
    @api.doc('upload_file')
    @api.expect(api.parser().add_argument('archivo', location='files', type='file', required=True, help='Archivo a importar'))
    @api.response(200, 'Importación exitosa')
    @api.response(400, 'Error en el archivo', error_model)
    @api.response(500, 'Error interno', error_model)
    @login_required
    def post(self):
        """Importar archivo de resultados de poker"""
        if 'archivo' not in request.files:
            return {'error': 'No se seleccionó archivo'}, 400
        
        archivo = request.files['archivo']
        if archivo.filename == '':
            return {'error': 'No se seleccionó archivo'}, 400
        
        if not allowed_file(archivo.filename):
            return {'error': 'Tipo de archivo no permitido'}, 400
        
        try:
            # Guardar archivo
            filename = secure_filename(archivo.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename_with_timestamp = f"{timestamp}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename_with_timestamp)
            archivo.save(filepath)
            
            # Determinar tipo de archivo y procesar
            if filename.lower().endswith('.html'):
                resultados_importados, duplicados_encontrados, duplicados_detalle = procesar_archivo_pokerstars(filepath, current_user.id)
            else:
                resultados_importados, duplicados_encontrados, duplicados_detalle = procesar_archivo_wpn(filepath, current_user.id)
            
            # Mover archivo a procesados
            processed_filename = f"procesados_{filename_with_timestamp}"
            processed_filepath = os.path.join(app.config['PROCESADOS_FOLDER'], processed_filename)
            os.rename(filepath, processed_filepath)
            
            return {
                'mensaje': f'Archivo procesado exitosamente. {resultados_importados} registros importados, {duplicados_encontrados} duplicados omitidos.',
                'resultados_importados': resultados_importados,
                'duplicados_encontrados': duplicados_encontrados,
                'duplicados_detalle': duplicados_detalle
            }
            
        except Exception as e:
            return {'error': f'Error procesando archivo: {str(e)}'}, 500

@import_ns.route('/files')
class ImportFiles(Resource):
    @api.doc('list_imported_files')
    @api.response(200, 'Archivos obtenidos exitosamente')
    @api.response(401, 'No autenticado', error_model)
    @api.response(500, 'Error interno', error_model)
    @login_required
    def get(self):
        """Listar archivos importados por el usuario"""
        try:
            # Obtener archivos del directorio de uploads
            upload_folder = app.config['UPLOAD_FOLDER']
            if not os.path.exists(upload_folder):
                return {'archivos': []}
            
            archivos = []
            for filename in os.listdir(upload_folder):
                if filename.endswith(('.xlsx', '.xls')):
                    filepath = os.path.join(upload_folder, filename)
                    stat = os.stat(filepath)
                    archivos.append({
                        'nombre': filename,
                        'tamaño': stat.st_size,
                        'fecha_modificacion': datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
            
            # Ordenar por fecha de modificación (más reciente primero)
            archivos.sort(key=lambda x: x['fecha_modificacion'], reverse=True)
            
            return {'archivos': archivos}
            
        except Exception as e:
            return {'error': f'Error al listar archivos: {str(e)}'}, 500

@import_ns.route('/status')
class ImportStatus(Resource):
    @api.doc('get_import_status')
    @api.response(200, 'Estado de importación obtenido exitosamente')
    @api.response(401, 'No autenticado', error_model)
    @api.response(500, 'Error interno', error_model)
    @login_required
    def get(self):
        """Obtener estado de la última importación"""
        try:
            # Obtener estadísticas de importación del usuario
            total_registros = PokerResult.query.filter_by(user_id=current_user.id).count()
            ultimo_registro = PokerResult.query.filter_by(user_id=current_user.id).order_by(
                PokerResult.fecha.desc(), PokerResult.hora.desc()
            ).first()
            
            estadisticas = {
                'total_registros': total_registros,
                'ultimo_registro': {
                    'fecha': ultimo_registro.fecha.isoformat() if ultimo_registro else None,
                    'hora': ultimo_registro.hora.isoformat() if ultimo_registro and ultimo_registro.hora else None,
                    'descripcion': ultimo_registro.descripcion if ultimo_registro else None
                } if ultimo_registro else None
            }
            
            return estadisticas
            
        except Exception as e:
            return {'error': f'Error al obtener estado: {str(e)}'}, 500

@reports_ns.route('/options')
class InformesOpciones(Resource):
    @api.doc('get_filter_options')
    @api.response(200, 'Opciones obtenidas exitosamente', opciones_model)
    @api.response(401, 'No autenticado', error_model)
    @api.response(500, 'Error interno', error_model)
    @require_auth_or_session
    def get(self):
        """Obtener opciones disponibles para filtros"""
        try:
            # Obtener opciones únicas del usuario actual
            response = supabase.table('poker_results').select('categoria, tipo_juego, nivel_buyin, sala').eq('user_id', current_user.id).execute()
            
            if not response.data:
                return {
                    'categorias': [],
                    'tipos_juego': [],
                    'niveles_buyin': [],
                    'salas': []
                }
            
            # Procesar datos
            categorias = list(set([r['categoria'] for r in response.data if r['categoria']]))
            tipos_juego = list(set([r['tipo_juego'] for r in response.data if r['tipo_juego']]))
            niveles_buyin = list(set([r['nivel_buyin'] for r in response.data if r['nivel_buyin']]))
            salas = list(set([r['sala'] for r in response.data if r['sala']]))
            
            return {
                'categorias': categorias,
                'tipos_juego': tipos_juego,
                'niveles_buyin': niveles_buyin,
                'salas': salas
            }
            
        except Exception as e:
            return {'error': f'Error al obtener opciones: {str(e)}'}, 500

@reports_ns.route('/results')
class InformesResultados(Resource):
    @api.doc('get_filtered_results')
    @api.expect(api.parser()
                .add_argument('categoria', type=str, help='Filtrar por categoría')
                .add_argument('tipo_juego', type=str, help='Filtrar por tipo de juego')
                .add_argument('nivel_buyin', type=str, help='Filtrar por nivel de buy-in')
                .add_argument('sala', type=str, help='Filtrar por sala')
                .add_argument('fecha_inicio', type=str, help='Fecha de inicio (YYYY-MM-DD)')
                .add_argument('fecha_fin', type=str, help='Fecha de fin (YYYY-MM-DD)')
                .add_argument('page', type=int, default=1, help='Número de página')
                .add_argument('per_page', type=int, default=50, help='Registros por página'))
    @api.response(200, 'Resultados obtenidos exitosamente')
    @api.response(401, 'No autenticado', error_model)
    @api.response(500, 'Error interno', error_model)
    @require_auth_or_session
    def get(self):
        """Obtener resultados filtrados con estadísticas y gráfico de últimos 10 días"""
        try:
            # Obtener parámetros de filtro
            args = request.args
            categoria = args.get('categoria')
            tipo_juego = args.get('tipo_juego')
            nivel_buyin = args.get('nivel_buyin')
            sala = args.get('sala')
            fecha_inicio = args.get('fecha_inicio')
            fecha_fin = args.get('fecha_fin')
            page = int(args.get('page', 1))
            per_page = int(args.get('per_page', 50))
            
            # Construir query base para el usuario actual
            query = supabase.table('poker_results').select('*').eq('user_id', current_user.id)
            
            # Aplicar filtros
            if categoria:
                query = query.eq('categoria', categoria)
            if tipo_juego:
                query = query.eq('tipo_juego', tipo_juego)
            if nivel_buyin:
                query = query.eq('nivel_buyin', nivel_buyin)
            if sala:
                query = query.eq('sala', sala)
            if fecha_inicio:
                query = query.gte('fecha', fecha_inicio)
            if fecha_fin:
                query = query.lte('fecha', fecha_fin)
            
            # Aplicar paginación
            offset = (page - 1) * per_page
            response = query.range(offset, offset + per_page - 1).execute()
            
            # Calcular estadísticas básicas
            stats_response = supabase.table('poker_results').select('importe, categoria, tipo_movimiento').eq('user_id', current_user.id).execute()
            
            total_registros = len(stats_response.data)
            suma_importes = sum(float(r['importe']) for r in stats_response.data)
            total_torneos = len([r for r in stats_response.data if r['categoria'] == 'Torneo'])
            
            # Calcular resultados diarios de los últimos 10 días (SIN FILTROS, desde fecha actual)
            from datetime import timedelta
            
            # Obtener los últimos 10 días calendario desde HOY
            hoy = datetime.now().date()
            ultimos_10_dias = [hoy - timedelta(days=i) for i in range(10)]
            ultimos_10_dias.reverse()  # Ordenar de más antiguo a más reciente
            
            # Obtener TODOS los movimientos de poker del usuario (sin filtros de fecha) para el gráfico
            todos_movimientos_poker = supabase.table('poker_results').select('*').eq('user_id', current_user.id).neq('categoria', 'Transferencia').neq('categoria', 'Depósito').neq('tipo_movimiento', 'Retiro').execute()
            
            # Calcular resultado por día (incluir días sin datos como 0)
            resultados_diarios = []
            for fecha in ultimos_10_dias:
                # Filtrar movimientos de poker para esta fecha específica
                movimientos_dia = [r for r in todos_movimientos_poker.data if r['fecha'] == fecha.isoformat()]
                resultado_dia = sum(float(r['importe']) for r in movimientos_dia)
                resultados_diarios.append({
                    'fecha': fecha.isoformat(),
                    'resultado': resultado_dia,
                    'movimientos': len(movimientos_dia)
                })
            
            return {
                'resultados': response.data,
                'paginacion': {
                    'pagina_actual': page,
                    'por_pagina': per_page,
                    'total_registros': total_registros
                },
                'estadisticas': {
                    'total_registros': total_registros,
                    'total_torneos': total_torneos,
                    'suma_importes': suma_importes,
                    'resultado_economico': suma_importes
                },
                'resultados_diarios': resultados_diarios
            }
            
        except Exception as e:
            return {'error': f'Error al obtener resultados: {str(e)}'}, 500

@admin_ns.route('/delete-all')
class EliminarTodos(Resource):
    @api.doc('delete_all_records')
    @api.response(200, 'Registros eliminados exitosamente')
    @api.response(500, 'Error interno', error_model)
    @login_required
    def post(self):
        """Eliminar todos los registros del usuario actual"""
        try:
            # Contar registros del usuario antes de eliminar
            response = supabase.table('poker_results').select('id').eq('user_id', current_user.id).execute()
            total_registros = len(response.data)
            
            if total_registros == 0:
                return {
                    'mensaje': 'No se encontraron registros para eliminar',
                    'registros_eliminados': 0
                }
            
            # Eliminar todos los registros del usuario
            supabase.table('poker_results').delete().eq('user_id', current_user.id).execute()
            
            return {
                'mensaje': f'Se eliminaron {total_registros} registros exitosamente',
                'registros_eliminados': total_registros
            }
            
        except Exception as e:
            return {'error': f'Error al eliminar registros: {str(e)}'}, 500

@admin_ns.route('/delete-by-room')
class EliminarPorSala(Resource):
    @api.doc('delete_records_by_room')
    @api.expect(api.parser().add_argument('sala', type=str, required=True, help='Sala a eliminar'))
    @api.response(200, 'Registros eliminados exitosamente')
    @api.response(400, 'Sala no encontrada', error_model)
    @api.response(500, 'Error interno', error_model)
    @login_required
    def post(self):
        """Eliminar registros de una sala específica del usuario actual"""
        args = request.get_json() or {}
        sala = args.get('sala')
        
        if not sala:
            return {'error': 'Sala es requerida'}, 400
        
        try:
            # Contar registros de la sala antes de eliminar
            response = supabase.table('poker_results').select('id').eq('user_id', current_user.id).eq('sala', sala).execute()
            total_registros = len(response.data)
            
            if total_registros == 0:
                return {'error': f'No se encontraron registros para la sala: {sala}'}, 400
            
            # Eliminar registros de la sala específica
            supabase.table('poker_results').delete().eq('user_id', current_user.id).eq('sala', sala).execute()
            
            return {
                'mensaje': f'Se eliminaron {total_registros} registros de la sala {sala} exitosamente',
                'registros_eliminados': total_registros,
                'sala': sala
            }
            
        except Exception as e:
            return {'error': f'Error al eliminar registros de la sala: {str(e)}'}, 500

@admin_ns.route('/available-rooms')
class SalasDisponibles(Resource):
    @api.doc('get_available_rooms')
    @api.response(200, 'Salas obtenidas exitosamente')
    @api.response(500, 'Error interno', error_model)
    @login_required
    def get(self):
        """Obtener las salas disponibles del usuario actual"""
        try:
            response = supabase.table('poker_results').select('sala').eq('user_id', current_user.id).execute()
            
            # Contar registros por sala del usuario
            salas_stats = {}
            for r in response.data:
                sala = r['sala']
                if sala not in salas_stats:
                    salas_stats[sala] = 0
                salas_stats[sala] += 1
            
            salas_info = [
                {
                    'sala': sala,
                    'registros': count
                } for sala, count in salas_stats.items() if sala
            ]
            
            return {'salas': salas_info}
            
        except Exception as e:
            return {'error': f'Error al obtener salas: {str(e)}'}, 500

@admin_ns.route('/stats')
class AdminStats(Resource):
    @api.doc('get_admin_stats')
    @api.response(200, 'Estadísticas obtenidas exitosamente')
    @api.response(401, 'No autenticado', error_model)
    @api.response(500, 'Error interno', error_model)
    @require_auth_or_session
    def get(self):
        """Obtener estadísticas generales del usuario"""
        try:
            # Obtener todos los registros del usuario
            response = supabase.table('poker_results').select('*').eq('user_id', current_user.id).execute()
            
            if not response.data:
                return {
                    'usuario': current_user.username,
                    'total_registros': 0,
                    'total_torneos': 0,
                    'rango_fechas': {'inicio': None, 'fin': None},
                    'estadisticas_por_sala': [],
                    'estadisticas_por_categoria': []
                }
            
            # Calcular estadísticas básicas
            total_registros = len(response.data)
            total_torneos = len([r for r in response.data if r['categoria'] == 'Torneo'])
            
            # Estadísticas por sala
            salas_stats = {}
            for r in response.data:
                sala = r['sala']
                if sala not in salas_stats:
                    salas_stats[sala] = {'registros': 0, 'total_importe': 0}
                salas_stats[sala]['registros'] += 1
                salas_stats[sala]['total_importe'] += float(r['importe'])
            
            # Estadísticas por categoría
            categorias_stats = {}
            for r in response.data:
                categoria = r['categoria']
                if categoria not in categorias_stats:
                    categorias_stats[categoria] = {'registros': 0, 'total_importe': 0}
                categorias_stats[categoria]['registros'] += 1
                categorias_stats[categoria]['total_importe'] += float(r['importe'])
            
            # Rango de fechas
            fechas = [r['fecha'] for r in response.data if r['fecha']]
            fecha_min = min(fechas) if fechas else None
            fecha_max = max(fechas) if fechas else None
            
            return {
                'usuario': current_user.username,
                'total_registros': total_registros,
                'total_torneos': total_torneos,
                'rango_fechas': {
                    'inicio': fecha_min,
                    'fin': fecha_max
                },
                'estadisticas_por_sala': [
                    {
                        'sala': sala,
                        'registros': stats['registros'],
                        'total_importe': stats['total_importe']
                    } for sala, stats in salas_stats.items() if sala
                ],
                'estadisticas_por_categoria': [
                    {
                        'categoria': categoria,
                        'registros': stats['registros'],
                        'total_importe': stats['total_importe']
                    } for categoria, stats in categorias_stats.items()
                ]
            }
            
        except Exception as e:
            return {'error': f'Error al obtener estadísticas: {str(e)}'}, 500

@analysis_ns.route('/insights')
class AnalisisInsights(Resource):
    @api.doc('get_analysis_insights')
    @api.response(200, 'Análisis obtenido exitosamente')
    @api.response(400, 'No hay datos para analizar', error_model)
    @api.response(500, 'Error interno', error_model)
    @login_required
    def get(self):
        """Análisis avanzado con insights para gestión del juego"""
        try:
            # Obtener todos los registros de torneos del usuario actual
            response = supabase.table('poker_results').select('*').eq('user_id', current_user.id).eq('categoria', 'Torneo').execute()
            
            if not response.data:
                return {'error': 'No hay datos de torneos para analizar'}, 400
            
            # Convertir a objetos similares a los de SQLAlchemy para compatibilidad
            torneos = [TorneoResult(r) for r in response.data]
            
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
            
            return {
                'analisis_buyin': analisis_buyin,
                'analisis_sala': analisis_sala,
                'analisis_temporal': analisis_temporal,
                'analisis_juego': analisis_juego,
                'analisis_consistencia': analisis_consistencia,
                'recomendaciones': recomendaciones
            }
            
        except Exception as e:
            return {'error': f'Error en análisis: {str(e)}'}, 500

@analysis_ns.route('/buyin')
class AnalisisBuyin(Resource):
    @api.doc('get_buyin_analysis')
    @api.response(200, 'Análisis por buy-in obtenido exitosamente')
    @api.response(400, 'No hay datos para analizar', error_model)
    @api.response(500, 'Error interno', error_model)
    @login_required
    def get(self):
        """Análisis de rendimiento por nivel de buy-in"""
        try:
            response = supabase.table('poker_results').select('*').eq('user_id', current_user.id).eq('categoria', 'Torneo').execute()
            
            if not response.data:
                return {'error': 'No hay datos de torneos para analizar'}, 400
            
            torneos = [TorneoResult(r) for r in response.data]
            analisis = analizar_rendimiento_por_buyin(torneos)
            return analisis
            
        except Exception as e:
            return {'error': f'Error en análisis por buy-in: {str(e)}'}, 500

@analysis_ns.route('/sala')
class AnalisisSala(Resource):
    @api.doc('get_sala_analysis')
    @api.response(200, 'Análisis por sala obtenido exitosamente')
    @api.response(400, 'No hay datos para analizar', error_model)
    @api.response(500, 'Error interno', error_model)
    @login_required
    def get(self):
        """Análisis de rendimiento por sala"""
        try:
            response = supabase.table('poker_results').select('*').eq('user_id', current_user.id).eq('categoria', 'Torneo').execute()
            
            if not response.data:
                return {'error': 'No hay datos de torneos para analizar'}, 400
            
            torneos = [TorneoResult(r) for r in response.data]
            analisis = analizar_rendimiento_por_sala(torneos)
            return analisis
            
        except Exception as e:
            return {'error': f'Error en análisis por sala: {str(e)}'}, 500

@analysis_ns.route('/temporal')
class AnalisisTemporal(Resource):
    @api.doc('get_temporal_analysis')
    @api.response(200, 'Análisis temporal obtenido exitosamente')
    @api.response(400, 'No hay datos para analizar', error_model)
    @api.response(500, 'Error interno', error_model)
    @login_required
    def get(self):
        """Análisis de patrones temporales"""
        try:
            response = supabase.table('poker_results').select('*').eq('user_id', current_user.id).eq('categoria', 'Torneo').execute()
            
            if not response.data:
                return {'error': 'No hay datos de torneos para analizar'}, 400
            
            torneos = [TorneoResult(r) for r in response.data]
            analisis = analizar_patrones_temporales(torneos)
            return analisis
            
        except Exception as e:
            return {'error': f'Error en análisis temporal: {str(e)}'}, 500

@analysis_ns.route('/juego')
class AnalisisJuego(Resource):
    @api.doc('get_juego_analysis')
    @api.response(200, 'Análisis por tipo de juego obtenido exitosamente')
    @api.response(400, 'No hay datos para analizar', error_model)
    @api.response(500, 'Error interno', error_model)
    @login_required
    def get(self):
        """Análisis de rendimiento por tipo de juego"""
        try:
            response = supabase.table('poker_results').select('*').eq('user_id', current_user.id).eq('categoria', 'Torneo').execute()
            
            if not response.data:
                return {'error': 'No hay datos de torneos para analizar'}, 400
            
            torneos = [TorneoResult(r) for r in response.data]
            analisis = analizar_rendimiento_por_juego(torneos)
            return analisis
            
        except Exception as e:
            return {'error': f'Error en análisis por juego: {str(e)}'}, 500

@analysis_ns.route('/consistencia')
class AnalisisConsistencia(Resource):
    @api.doc('get_consistencia_analysis')
    @api.response(200, 'Análisis de consistencia obtenido exitosamente')
    @api.response(400, 'No hay datos para analizar', error_model)
    @api.response(500, 'Error interno', error_model)
    @login_required
    def get(self):
        """Análisis de consistencia del jugador"""
        try:
            response = supabase.table('poker_results').select('*').eq('user_id', current_user.id).eq('categoria', 'Torneo').execute()
            
            if not response.data:
                return {'error': 'No hay datos de torneos para analizar'}, 400
            
            torneos = [TorneoResult(r) for r in response.data]
            analisis = analizar_consistencia_jugador(torneos)
            return analisis
            
        except Exception as e:
            return {'error': f'Error en análisis de consistencia: {str(e)}'}, 500

# =============================================================================
# FUNCIONES DE ANÁLISIS
# =============================================================================

class TorneoResult:
    """Clase auxiliar para compatibilidad con las funciones de análisis"""
    def __init__(self, data):
        self.fecha = datetime.strptime(data['fecha'], '%Y-%m-%d').date() if isinstance(data['fecha'], str) else data['fecha']
        self.hora = datetime.strptime(data['hora'], '%H:%M:%S').time() if data['hora'] and isinstance(data['hora'], str) else data['hora']
        self.importe = float(data['importe'])
        self.nivel_buyin = data['nivel_buyin']
        self.sala = data['sala']
        self.tipo_juego = data['tipo_juego']
        self.descripcion = data['descripcion']


if __name__ == '__main__':
    print("🚀 Iniciando aplicación funcional con Supabase...")
    print(f"📡 Supabase URL: {SUPABASE_URL}")
    print(f"🔑 Supabase Key: {SUPABASE_KEY[:20]}...")
    
    app.run(debug=False, host='0.0.0.0', port=5001)
