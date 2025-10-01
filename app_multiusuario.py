#!/usr/bin/env python3
"""
Aplicación de análisis de resultados de poker - Versión Multiusuario
Configurada para Supabase y despliegue en Vercel
"""

import os
import hashlib
import pandas as pd
from datetime import datetime, date, time, timedelta
from collections import defaultdict
import statistics
import requests
from bs4 import BeautifulSoup
import json
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, Response
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SelectField, SubmitField, DateField, IntegerField
from wtforms.validators import DataRequired, Length, Email, EqualTo
from dotenv import load_dotenv

# Importar Flask-RESTX para Swagger
from flask_restx import Api, Resource, fields, Namespace

# Importar Supabase
from supabase import create_client, Client

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get(
    'SECRET_KEY', 'dev-secret-key-change-in-production')

# Configuración de archivos
UPLOAD_FOLDER = 'uploads'
PROCESADOS_FOLDER = 'procesados'
ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'html'}

# Crear carpetas si no existen
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESADOS_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESADOS_FOLDER'] = PROCESADOS_FOLDER

# Configurar Swagger/OpenAPI
app.config['RESTX_MASK_SWAGGER'] = False
app.config['SWAGGER_UI_DOC_EXPANSION'] = 'list'
app.config['SWAGGER_UI_OPERATION_ID'] = True
app.config['SWAGGER_UI_REQUEST_DURATION'] = True

# Inicializar extensiones
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor, inicia sesión para acceder a esta página.'

# Configurar Supabase
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError(
        "SUPABASE_URL y SUPABASE_KEY deben estar configurados en el archivo .env")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Configurar API con Swagger
api = Api(
    app,
    version='1.0',
    title='Poker Results API',
    description='API para análisis y gestión de resultados de poker',
    doc='/swagger/',
    prefix='/api',
    authorizations={
        'Bearer': {
            'type': 'apiKey',
            'in': 'header',
            'name': 'Authorization',
            'description': 'Token de autenticación (Bearer token)'
        }
    },
    security='Bearer'
)

# Definir namespaces para organizar endpoints
reports_ns = Namespace('reports', description='Informes y estadísticas')
api.add_namespace(reports_ns, path='/api/reports')

# =============================================================================
# MODELOS DE DATOS PARA SWAGGER
# =============================================================================

# Modelo para resultado diario
resultado_diario_model = api.model('ResultadoDiario', {
    'fecha': fields.String(description='Fecha (YYYY-MM-DD)'),
    'resultado': fields.Float(description='Resultado del día'),
    'movimientos': fields.Integer(description='Cantidad de movimientos')
})

# Modelo para respuesta de últimos 10 días
last_10_days_response_model = api.model('Last10DaysResponse', {
    'resultados_diarios': fields.List(fields.Nested(resultado_diario_model), description='Resultados de últimos 10 días'),
    'total_dias': fields.Integer(description='Total de días (siempre 10)'),
    'fecha_inicio': fields.String(description='Fecha de inicio del período'),
    'fecha_fin': fields.String(description='Fecha de fin del período')
})

# Modelo de error
error_model = api.model('Error', {
    'error': fields.String(description='Mensaje de error')
})

# =============================================================================
# FORMULARIOS
# =============================================================================


class LoginForm(FlaskForm):
    """Formulario de login"""
    username = StringField(
    'Usuario', validators=[
        DataRequired(), Length(
            min=3, max=20)])
    password = PasswordField('Contraseña', validators=[DataRequired()])
    remember_me = BooleanField('Recordarme')
    submit = SubmitField('Iniciar Sesión')


class UserForm(FlaskForm):
    """Formulario para crear/editar usuarios"""
    username = StringField(
    'Usuario', validators=[
        DataRequired(), Length(
            min=3, max=20)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField(
    'Contraseña', validators=[
        DataRequired(), Length(
            min=6)])
    password2 = PasswordField(
    'Confirmar Contraseña', validators=[
        DataRequired(), EqualTo('password')])
    is_admin = BooleanField('Es Administrador')
    is_active = BooleanField('Usuario Activo', default=True)
    submit = SubmitField('Guardar Usuario')


class ChangePasswordForm(FlaskForm):
    """Formulario para cambiar contraseña"""
    current_password = PasswordField(
    'Contraseña Actual', validators=[
        DataRequired()])
    new_password = PasswordField(
    'Nueva Contraseña', validators=[
        DataRequired(), Length(
            min=6)])
    new_password2 = PasswordField(
    'Confirmar Nueva Contraseña', validators=[
        DataRequired(), EqualTo('new_password')])
    submit = SubmitField('Cambiar Contraseña')


class AdminUserSelectForm(FlaskForm):
    """Formulario para seleccionar usuario en análisis de admin"""
    user_id = SelectField(
    'Seleccionar Usuario',
    coerce=int,
    validators=[
        DataRequired()])
    submit = SubmitField('Ver Análisis')

# =============================================================================
# FUNCIONES DE UTILIDAD
# =============================================================================


@login_manager.user_loader
def load_user(user_id):
    """Cargar usuario para Flask-Login desde Supabase"""
    try:
        # Buscar usuario en Supabase por ID (UUID)
        response = supabase.table('users').select(
            '*').eq('id', user_id).execute()

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


def allowed_file(filename):
    """Verificar si el archivo tiene extensión permitida"""
    return '.' in filename and filename.rsplit(
        '.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_user_poker_results(user_id, filters=None):
    """Obtener resultados de poker de un usuario desde Supabase"""
    try:
        query = supabase.table('poker_results').select(
            '*').eq('user_id', user_id)

        if filters:
            if 'fecha_inicio' in filters:
                query = query.gte('fecha', filters['fecha_inicio'])
            if 'fecha_fin' in filters:
                query = query.lte('fecha', filters['fecha_fin'])
            if 'tipo_movimiento' in filters:
                query = query.eq('tipo_movimiento', filters['tipo_movimiento'])
            if 'monto_minimo' in filters:
                query = query.gte('importe', filters['monto_minimo'])
            if 'categorias' in filters:
                query = query.in_('categoria', filters['categorias'])
            if 'tipos_juego' in filters:
                query = query.in_('tipo_juego', filters['tipos_juego'])
            if 'niveles_buyin' in filters:
                query = query.in_('nivel_buyin', filters['niveles_buyin'])
            if 'salas' in filters:
                query = query.in_('sala', filters['salas'])

        response = query.execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Error obteniendo resultados de poker: {e}")
        return []


def create_poker_result(user_id, data):
    """Crear un nuevo registro de poker en Supabase"""
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
        print(f"Error creando registro de poker: {e}")
        return None


def delete_user_poker_results(user_id):
    """Eliminar todos los registros de poker de un usuario"""
    try:
        response = supabase.table('poker_results').delete().eq(
            'user_id', user_id).execute()
        return len(response.data) if response.data else 0
    except Exception as e:
        print(f"Error eliminando registros de poker: {e}")
        return 0


def bulk_insert_poker_results(user_id, records):
    """Insertar múltiples registros de poker en Supabase"""
    try:
        # Preparar los datos para inserción masiva
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
            response = supabase.table(
                'poker_results').insert(poker_data).execute()
            return len(response.data) if response.data else 0
        return 0
    except Exception as e:
        print(f"Error insertando registros masivos: {e}")
        return 0


def get_user_distinct_values(user_id, column):
    """Obtener valores únicos de una columna para un usuario"""
    try:
        response = supabase.table('poker_results').select(
            column).eq('user_id', user_id).execute()
        data = response.data if response.data else []
        unique_values = list(set([item[column]
                             for item in data if item[column]]))
        return unique_values
    except Exception as e:
        print(f"Error obteniendo valores únicos: {e}")
        return []


def generar_hash_duplicado(
    fecha,
    hora,
    descripcion,
    importe,
    payment_method=None,
    money_in=None,
     money_out=None):
    """Generar hash único para detectar duplicados"""
    # Crear string único combinando todos los campos relevantes
    fecha_str = fecha.strftime(
        '%Y-%m-%d') if isinstance(fecha, date) else str(fecha)
    hora_str = hora.strftime('%H:%M:%S') if hora else '00:00:00'

    # Incluir todos los campos en el hash
    campos = [
        fecha_str,
        hora_str,
        descripcion,
        str(importe),
        payment_method or '',
        str(money_in or 0),
        str(money_out or 0)
    ]

    string_unico = '|'.join(campos)
    return hashlib.sha256(string_unico.encode()).hexdigest()


def clasificar_nivel_buyin(importe):
    """Clasificar nivel de buy-in basado en el importe"""
    if importe <= 5:
        return 'Micro'
    elif importe <= 25:
        return 'Bajo'
    elif importe <= 100:
        return 'Medio'
    else:
        return 'Alto'

# =============================================================================
# FUNCIONES DE CATEGORIZACIÓN (MANTENIDAS DEL CÓDIGO ORIGINAL)
# =============================================================================


def categorizar_movimiento(payment_method, descripcion, money_in, money_out):
    """Categorizar movimientos de WPN"""
    payment_lower = payment_method.lower() if payment_method else ''
    desc_lower = descripcion.lower() if descripcion else ''

    # Mapeo de tipos de movimiento
    tipo_movimiento_map = {
        'buy in': 'Buy In',
        'winnings': 'Winnings',
        'bounty': 'Bounty',
        'fee': 'Fee',
        'reentry fee': 'Reentry Fee',
        'money added': 'Money Added',
        'money out': 'Money Out',
        'money in': 'Money In',
        'payout': 'Payout',
        'reentry buy in': 'Reentry Buy In',
        'unregister buy in': 'Unregister Buy In',
        'unregister fee': 'Unregister Fee',
        'sit & crush jackpot': 'Sit & Crush Jackpot'
    }

    tipo_movimiento = tipo_movimiento_map.get(payment_lower, payment_method)

    # Determinar categoría
    if 'tournament' in desc_lower or 'bounty' in desc_lower or 'fee' in desc_lower or 'reentry' in desc_lower or 'sit & crush' in desc_lower or 'unregister' in desc_lower or 'on demand' in desc_lower:
        categoria = 'Torneo'
    elif 'money added' in payment_lower or 'money out' in payment_lower or 'money in' in payment_lower:
        categoria = 'Cash'
    elif 'transfer' in payment_lower:
        categoria = 'Transferencia'
    elif 'withdrawal' in payment_lower:
        categoria = 'Retiro'
    elif 'deposit' in payment_lower:
        categoria = 'Depósito'
    else:
        categoria = 'Otro'

    # Regla especial para Payout
    if tipo_movimiento == 'Payout':
        categoria = 'Retiro'

    # Determinar tipo de juego
    if categoria == 'Torneo':
        if 'sit & go' in desc_lower:
            tipo_juego = 'Sit & Go'
        elif 'plo' in desc_lower or 'omaha' in desc_lower:
            if 'hi/lo' in desc_lower or 'hi lo' in desc_lower:
                if '5c' in desc_lower or '5 card' in desc_lower:
                    tipo_juego = '5C PLO8'
                elif '8' in desc_lower:
                    tipo_juego = 'PLO8'
                else:
                    tipo_juego = 'PLO Hi/Lo'
            elif '8' in desc_lower:
                tipo_juego = 'PLO8'
            else:
                tipo_juego = 'PLO'
        elif 'stud' in desc_lower:
            if 'hi/lo' in desc_lower or 'hi lo' in desc_lower:
                tipo_juego = 'Stud Hi/Lo'
            else:
                tipo_juego = 'Stud'
        elif 'nlh' in desc_lower or 'holdem' in desc_lower or 'nl hold' in desc_lower:
            tipo_juego = 'NLH'
        elif 'nlo8' in desc_lower:
            tipo_juego = 'NLO8'
        else:
            tipo_juego = 'Torneo'
    elif categoria == 'Cash':
        if 'stud' in desc_lower and (
    'hi/lo' in desc_lower or 'hi lo' in desc_lower):
            tipo_juego = 'Stud Hi/Lo'
        elif 'nlo8' in desc_lower:
            tipo_juego = 'NLO8'
        else:
            tipo_juego = 'Cash'
    else:
        tipo_juego = 'Otro'

    return categoria, tipo_movimiento, tipo_juego


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
            # Si hay información en Game pero no coincide con patrones
            # conocidos
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

# =============================================================================
# FUNCIONES DE RECLASIFICACIÓN (MANTENIDAS DEL CÓDIGO ORIGINAL)
# =============================================================================


def reclasificar_niveles_buyin_automatica():
    """Reclasifica automáticamente los niveles de buy-in para registros de torneos"""
    # Usar contexto de aplicación para las operaciones de base de datos
    with app.app_context():
        try:
            # Obtener todos los registros de torneos con Buy In que ya tienen
            # nivel_buyin
            # Obtener datos usando Supabase
            filtros_buyin = {
                'categorias': ['Torneo'],
                'tipo_movimiento': 'Buy In'
            }
            buyins_data = get_user_poker_results(
                current_user.id, filtros_buyin)
            buyins_clasificados = [
    r for r in buyins_data if r.get('nivel_buyin')]

            if not buyins_clasificados:
                return 0

            # Obtener registros de torneos sin clasificar
            # Obtener datos usando Supabase - registros sin clasificar
            filtros_sin_clasificar = {
                'categorias': ['Torneo']
            }
            sin_clasificar_data = get_user_poker_results(
                current_user.id, filtros_sin_clasificar)
            registros_sin_clasificar = [
    r for r in sin_clasificar_data if not r.get('nivel_buyin')]

            if not registros_sin_clasificar:
                return 0

            # Crear diccionario de descripción -> nivel_buyin
            descripcion_nivel = {}
            for buyin in buyins_clasificados:
                descripcion_nivel[buyin.descripcion] = buyin.nivel_buyin

            reclasificados = 0
            for registro in registros_sin_clasificar:
                try:
                    nivel_buyin = None

                    # Método 1: Búsqueda exacta por descripción
                    if registro.descripcion in descripcion_nivel:
                        nivel_buyin = descripcion_nivel[registro.descripcion]
                    else:
                        # Método 2: Búsqueda por ID del torneo
                        partes = registro.descripcion.split(' ', 1)
                        if len(partes) > 1:
                            torneo_id = partes[0]
                            for buyin_desc, nivel in descripcion_nivel.items():
                                if buyin_desc.startswith(torneo_id + ' '):
                                    nivel_buyin = nivel
                                    break

                    # Método 3: Clasificar por importe si no se encuentra
                    # coincidencia
                    if not nivel_buyin:
                        nivel_buyin = clasificar_nivel_buyin(
                            abs(registro.importe))

                    if nivel_buyin:
                        registro.nivel_buyin = nivel_buyin
                        reclasificados += 1

                except Exception as e:
                    print(f"Error reclasificando registro {registro.id}: {e}")
                    continue

            if reclasificados > 0:
                db.session.commit()

            return reclasificados

        except Exception as e:
            print(f"Error en reclasificación automática: {e}")
            return 0


def reclasificar_tipos_juego_automatica():
    """Reclasifica automáticamente los tipos de juego para registros relacionados"""
    # Usar contexto de aplicación para las operaciones de base de datos
    with app.app_context():
        try:
            # Obtener todos los registros Buy In con tipo de juego específico
            # Obtener datos usando Supabase
            filtros_buyin = {
                'categorias': ['Torneo'],
                'tipo_movimiento': 'Buy In'
            }
            buyins_data = get_user_poker_results(
                current_user.id, filtros_buyin)
            buyins_clasificados = [
    r for r in buyins_data if r.get('tipo_juego') != 'Torneo']

            if not buyins_clasificados:
                return 0

            # Crear diccionario de descripción -> tipo_juego
            descripcion_tipo_juego = {}
            for buyin in buyins_clasificados:
                descripcion_tipo_juego[buyin.descripcion] = buyin.tipo_juego

            # Obtener registros que necesitan reclasificación
            # Obtener datos usando Supabase
            tipos_movimiento_reclasificar = [
                'Reentry Buy In', 'Winnings', 'Bounty', 'Fee', 'Reentry Fee',
                'Unregister Buy In', 'Unregister Fee', 'Sit & Crush Jackpot',
                'Tournament Rebuy', 'Ticket'
            ]
            filtros_reclasificar = {
                'categorias': ['Torneo'],
                'tipos_juego': ['Torneo']
            }
            reclasificar_data = get_user_poker_results(
                current_user.id, filtros_reclasificar)
            registros_sin_clasificar = [r for r in reclasificar_data if r.get(
                'tipo_movimiento') in tipos_movimiento_reclasificar]

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
                        # Método 2: Búsqueda por ID del torneo
                        partes = registro.descripcion.split(' ', 1)
                        if len(partes) > 1:
                            torneo_id = partes[0]
                            for buyin_desc, tipo in descripcion_tipo_juego.items():
                                if buyin_desc.startswith(torneo_id + ' '):
                                    tipo_juego = tipo
                                    break

                    if tipo_juego:
                        registro.tipo_juego = tipo_juego
                        reclasificados += 1

                except Exception as e:
                    print(
    f"Error reclasificando tipo de juego para registro {
        registro.id}: {e}")
                    continue

            if reclasificados > 0:
                db.session.commit()

            return reclasificados

        except Exception as e:
            print(f"Error en reclasificación de tipos de juego: {e}")
            return 0

# =============================================================================
# RUTAS DE AUTENTICACIÓN
# =============================================================================


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Página de login"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = LoginForm()
    if form.validate_on_submit():
        try:
            # Buscar usuario en Supabase
            response = supabase.table('users').select(
                '*').eq('username', form.username.data).execute()

            if response.data:
                user_data = response.data[0]

                # Verificar contraseña usando werkzeug
                if check_password_hash(
    user_data['password_hash'],
    form.password.data) and user_data.get(
        'is_active',
         True):
                    # Crear objeto User para Flask-Login
                    user = User(
                        id=user_data['id'],
                        username=user_data['username'],
                        email=user_data['email'],
                        is_admin=user_data.get('is_admin', False),
                        is_active=user_data.get('is_active', True)
                    )

                    login_user(user, remember=form.remember_me.data)

                    # Actualizar último login en Supabase
                    supabase.table('users').update({
                        'last_login': datetime.utcnow().isoformat()
                    }).eq('id', user_data['id']).execute()

                    next_page = request.args.get('next')
                    if not next_page or not next_page.startswith('/'):
                        next_page = url_for('index')
                    return redirect(next_page)
                else:
                    flash(
    'Usuario o contraseña incorrectos, o cuenta desactivada.',
     'error')
            else:
                flash(
    'Usuario o contraseña incorrectos, o cuenta desactivada.',
     'error')
        except Exception as e:
            print(f"Error en login: {e}")
            flash(
    'Error interno del servidor. Por favor, intenta de nuevo.',
     'error')

    return render_template('login.html', form=form)


@app.route('/logout')
@login_required
def logout():
    """Cerrar sesión"""
    logout_user()
    return redirect(url_for('login'))


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
            # Verificar si el usuario ya existe en Supabase
            existing_user_response = supabase.table('users').select(
                '*').eq('username', form.username.data).execute()
            if existing_user_response.data:
                flash(
    'El nombre de usuario ya existe. Por favor, elige otro.',
     'error')
                return render_template('register.html', form=form)

            existing_email_response = supabase.table('users').select(
                '*').eq('email', form.email.data).execute()
            if existing_email_response.data:
                flash(
    'El email ya está registrado. Por favor, usa otro email.',
     'error')
                return render_template('register.html', form=form)

            # Crear nuevo usuario en Supabase
            new_user_data = {
                'username': form.username.data,
                'email': form.email.data,
                'password_hash': generate_password_hash(form.password.data),
                'is_admin': False,
                'is_active': True,
                'created_at': datetime.utcnow().isoformat()
            }

            response = supabase.table('users').insert(new_user_data).execute()

            if response.data:
                flash(
    '¡Usuario registrado exitosamente! Ya puedes iniciar sesión.',
     'success')
                return redirect(url_for('login'))
            else:
                flash(
    'Error al registrar el usuario. Por favor, intenta de nuevo.',
     'error')
        except Exception as e:
            print(f"Error registrando usuario: {e}")
            flash(
    'Error al registrar el usuario. Por favor, intenta de nuevo.',
     'error')

    return render_template('register.html', form=form)

# =============================================================================
# RUTAS PRINCIPALES
# =============================================================================


@app.route('/')
@login_required
def index():
    """Página principal"""
    return render_template('index.html')


@app.route('/importar')
@login_required
def importar():
    """Página de importación"""
    return render_template('importar.html')


@app.route('/informes')
@login_required
def informes():
    """Página de informes"""
    return render_template('informes.html')


@app.route('/analisis')
@login_required
def analisis():
    """Página de análisis avanzado"""
    return render_template('analisis.html')

# =============================================================================
# RUTAS DE ADMINISTRACIÓN
# =============================================================================


@app.route('/admin')
@login_required
def admin():
    """Panel de administración"""
    if not current_user.is_admin:
        flash('No tienes permisos para acceder a esta página.', 'error')
        return redirect(url_for('index'))

    try:
        response = supabase.table('users').select('*').execute()
        users = response.data if response.data else []
        return render_template('admin.html', users=users)
    except Exception as e:
        print(f"Error obteniendo usuarios: {e}")
        flash('Error al cargar usuarios.', 'error')
        return redirect(url_for('index'))


@app.route('/admin/users')
@login_required
def admin_users():
    """Gestión de usuarios"""
    if not current_user.is_admin:
        flash('No tienes permisos para acceder a esta página.', 'error')
        return redirect(url_for('index'))

    try:
        response = supabase.table('users').select('*').execute()
        users = response.data if response.data else []
        return render_template('admin_users.html', users=users)
    except Exception as e:
        print(f"Error obteniendo usuarios: {e}")
        flash('Error al cargar usuarios.', 'error')
        return redirect(url_for('index'))


@app.route('/admin/users/new', methods=['GET', 'POST'])
@login_required
def admin_new_user():
    """Crear nuevo usuario"""
    if not current_user.is_admin:
        flash('No tienes permisos para acceder a esta página.', 'error')
        return redirect(url_for('index'))

    form = UserForm()
    if form.validate_on_submit():
        try:
            # Verificar si el usuario ya existe en Supabase
            existing_user_response = supabase.table('users').select(
                '*').eq('username', form.username.data).execute()
            if existing_user_response.data:
                flash('El nombre de usuario ya existe.', 'error')
                return render_template(
    'admin_user_form.html',
    form=form,
     title='Crear Usuario')

            existing_email_response = supabase.table('users').select(
                '*').eq('email', form.email.data).execute()
            if existing_email_response.data:
                flash('El email ya está registrado.', 'error')
                return render_template(
    'admin_user_form.html',
    form=form,
     title='Crear Usuario')

            # Crear nuevo usuario en Supabase
            new_user_data = {
                'username': form.username.data,
                'email': form.email.data,
                'password_hash': generate_password_hash(form.password.data),
                'is_admin': form.is_admin.data,
                'is_active': form.is_active.data,
                'created_at': datetime.utcnow().isoformat()
            }

            response = supabase.table('users').insert(new_user_data).execute()

            if response.data:
                flash('Usuario creado exitosamente.', 'success')
                return redirect(url_for('admin_users'))
            else:
                flash('Error al crear el usuario.', 'error')
        except Exception as e:
            print(f"Error creando usuario: {e}")
            flash('Error al crear el usuario.', 'error')

    return render_template(
    'admin_user_form.html',
    form=form,
     title='Crear Usuario')


@app.route('/admin/users/<user_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_edit_user(user_id):
    """Editar usuario"""
    if not current_user.is_admin:
        flash('No tienes permisos para acceder a esta página.', 'error')
        return redirect(url_for('index'))

    try:
        # Buscar usuario en Supabase
        response = supabase.table('users').select(
            '*').eq('id', user_id).execute()

        if not response.data:
            flash('Usuario no encontrado.', 'error')
            return redirect(url_for('admin_users'))

        user_data = response.data[0]
        # Crear objeto form temporal para pasar datos

        class TempForm:
            def __init__(self):
                self.username = user_data['username']
                self.email = user_data['email']
                self.is_admin = user_data.get('is_admin', False)
                self.is_active = user_data.get('is_active', True)
                self.password = ''

        temp_form = TempForm()
        form = UserForm(obj=temp_form)

        if form.validate_on_submit():
            # Verificar si el username ya existe en otro usuario
            existing_user_response = supabase.table('users').select(
                '*').eq('username', form.username.data).neq('id', user_id).execute()
            if existing_user_response.data:
                flash('El nombre de usuario ya existe.', 'error')
                return render_template(
    'admin_user_form.html',
    form=form,
    title='Editar Usuario',
     user=user_data)

            # Verificar si el email ya existe en otro usuario
            existing_email_response = supabase.table('users').select(
                '*').eq('email', form.email.data).neq('id', user_id).execute()
            if existing_email_response.data:
                flash('El email ya está registrado.', 'error')
                return render_template(
    'admin_user_form.html',
    form=form,
    title='Editar Usuario',
     user=user_data)

            # Preparar datos para actualizar
            update_data = {
                'username': form.username.data,
                'email': form.email.data,
                'is_admin': form.is_admin.data,
                'is_active': form.is_active.data
            }

            if form.password.data:  # Solo cambiar contraseña si se proporciona
                update_data['password_hash'] = generate_password_hash(
                    form.password.data)

            # Actualizar usuario en Supabase
            update_response = supabase.table('users').update(
                update_data).eq('id', user_id).execute()

            if update_response.data:
                flash('Usuario actualizado exitosamente.', 'success')
                return redirect(url_for('admin_users'))
            else:
                flash('Error al actualizar el usuario.', 'error')
    except Exception as e:
        print(f"Error editando usuario: {e}")
        flash('Error al editar el usuario.', 'error')

    return render_template(
    'admin_user_form.html',
    form=form,
    title='Editar Usuario',
     user=user)


@app.route('/admin/analisis')
@login_required
def admin_analisis():
    """Análisis de administrador con selección de usuario"""
    if not current_user.is_admin:
        flash('No tienes permisos para acceder a esta página.', 'error')
        return redirect(url_for('index'))

    form = AdminUserSelectForm()
    try:
        response = supabase.table('users').select(
            'id, username, email').eq('is_active', True).execute()
        users = response.data if response.data else []
        form.user_id.choices = [
            (u['id'], f"{u['username']} ({u['email']})") for u in users]
    except Exception as e:
        print(f"Error obteniendo usuarios para análisis: {e}")
        form.user_id.choices = []

    return render_template('admin_analisis.html', form=form)

# =============================================================================
# API ENDPOINTS (MODIFICADOS PARA MULTIUSUARIO)
# =============================================================================


@app.route('/api/importar', methods=['POST'])
@login_required
def api_importar():
    """API para importar archivos - Modificado para multiusuario"""
    if 'archivo' not in request.files:
        return jsonify({'error': 'No se seleccionó archivo'}), 400

    archivo = request.files['archivo']
    if archivo.filename == '':
        return jsonify({'error': 'No se seleccionó archivo'}), 400

    if not allowed_file(archivo.filename):
        return jsonify({'error': 'Tipo de archivo no permitido'}), 400

    try:
        # Guardar archivo
        filename = secure_filename(archivo.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename_with_timestamp = f"{timestamp}_{filename}"
        filepath = os.path.join(
    app.config['UPLOAD_FOLDER'],
     filename_with_timestamp)
        archivo.save(filepath)

        # Determinar tipo de archivo y procesar
        if filename.lower().endswith('.html'):
            resultados_importados, duplicados_encontrados, duplicados_detalle = procesar_archivo_pokerstars(
                filepath, current_user.id)
        else:
            resultados_importados, duplicados_encontrados, duplicados_detalle = procesar_archivo_wpn(
                filepath, current_user.id)

        # Mover archivo a procesados
        processed_filename = f"procesados_{filename_with_timestamp}"
        processed_filepath = os.path.join(
    app.config['PROCESADOS_FOLDER'], processed_filename)
        os.rename(filepath, processed_filepath)

        return jsonify({
            'mensaje': f'Archivo procesado exitosamente. {resultados_importados} registros importados, {duplicados_encontrados} duplicados omitidos.',
            'resultados_importados': resultados_importados,
            'duplicados_encontrados': duplicados_encontrados,
            'duplicados_detalle': duplicados_detalle
        })

    except Exception as e:
        return jsonify({'error': f'Error procesando archivo: {str(e)}'}), 500


@app.route('/api/previsualizar-archivo', methods=['POST'])
@login_required
def api_previsualizar_archivo():
    """API endpoint para previsualizar el archivo antes de la importación"""
    try:
        if 'archivo' not in request.files:
            return jsonify(
                {'error': 'No se ha seleccionado ningún archivo'}), 400

        archivo = request.files['archivo']
        sala = request.form.get('sala', '')

        if archivo.filename == '':
            return jsonify(
                {'error': 'No se ha seleccionado ningún archivo'}), 400

        if not sala:
            return jsonify({'error': 'Debe seleccionar una sala'}), 400

        # Leer el archivo para analizar
        archivo.seek(0)
        contenido_primeros_bytes = archivo.read(
            100).decode('utf-8', errors='ignore')
        archivo.seek(0)

        # Detectar si el archivo es realmente HTML (incluso con extensión
        # Excel)
        es_html = (archivo.filename.lower().endswith('.html') or
                  contenido_primeros_bytes.strip().upper().startswith('<HTML'))

        if es_html:
            # Archivo HTML de Pokerstars (incluso si tiene extensión Excel)
            try:
                content = archivo.read().decode('utf-8')
                soup = BeautifulSoup(content, 'html.parser')

                # Contar registros en HTML
                rows = soup.find_all('tr')
                # -1 para excluir header
                total_registros = len(rows) - 1 if rows else 0

                # Validar que se encontraron registros
                if total_registros == 0:
                    return jsonify(
                        {'error': 'No se encontraron registros válidos en el archivo HTML'}), 400

            except UnicodeDecodeError:
                return jsonify(
                    {'error': 'Error al leer el archivo HTML. Verifique que el archivo esté en formato UTF-8'}), 400
            except Exception as e:
                return jsonify(
                    {'error': f'Error al procesar el archivo HTML: {str(e)}'}), 400

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
                        raise Exception(
    f"No se pudo leer el archivo Excel. Errores: {
        '; '.join(error_motores)}")

                total_registros = len(df)

                # Filtrar registros sin fecha - manejar diferentes formatos de
                # columna
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
                return jsonify(
                    {'error': f'Error al procesar el archivo Excel: {str(e)}'}), 400

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
        return jsonify(
            {'error': f'Error al analizar el archivo: {str(e)}'}), 500


@app.route('/api/importar-progreso', methods=['POST'])
@login_required
def api_importar_progreso():
    """API endpoint para importar archivos con progreso en tiempo real usando SSE"""
    try:
        # El decorador @login_required ya verifica la autenticación
        user_id = current_user.id

        if 'archivo' not in request.files:
            return jsonify(
                {'error': 'No se ha seleccionado ningún archivo'}), 400

        archivo = request.files['archivo']
        sala = request.form.get('sala', '')

        if archivo.filename == '':
            return jsonify(
                {'error': 'No se ha seleccionado ningún archivo'}), 400

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
                    primeros_bytes = f.read(100).decode(
                        'utf-8', errors='ignore')

                es_html_real = primeros_bytes.strip().upper().startswith('<HTML')

                # Procesar archivo según la sala y tipo real
                if sala == 'WPN':
                    resultado = procesar_archivo_wpn_con_progreso_streaming(
                        filepath, user_id, progress_callback)
                elif sala == 'Pokerstars':
                    if es_html_real:
                        # Archivo HTML de PokerStars (incluso con extensión
                        # Excel)
                        resultado = procesar_archivo_pokerstars_con_progreso_streaming(
                            filepath, user_id, progress_callback)
                    else:
                        # Archivo Excel real de PokerStars
                        resultado = procesar_archivo_pokerstars_excel_con_progreso_streaming(
                            filepath, user_id, progress_callback)
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
        return jsonify(
            {'error': f'Error al procesar el archivo: {str(e)}'}), 500

# =============================================================================
# FUNCIONES DE PROCESAMIENTO DE ARCHIVOS
# =============================================================================


def generar_hash_duplicado(
    fecha,
    hora,
    payment_method,
    descripcion,
    money_in,
    money_out,
     sala):
    """Genera un hash único para detectar duplicados"""
    contenido = f"{fecha}_{hora}_{payment_method}_{descripcion}_{money_in}_{money_out}_{sala}"
    return hashlib.sha256(contenido.encode()).hexdigest()


def categorizar_movimiento(payment_category, payment_method, description):
    """Categoriza automáticamente los movimientos de WPN"""
    descripcion_lower = description.lower()
    payment_method_lower = payment_method.lower()

    # Categoría principal
    if 'tournament' in descripcion_lower or 'tourney' in descripcion_lower:
        categoria = 'Torneo'
    elif 'cash' in descripcion_lower or 'ring' in descripcion_lower:
        categoria = 'Cash'
    elif 'sit' in descripcion_lower and 'go' in descripcion_lower:
        categoria = 'Sit & Go'
    else:
        categoria = 'Otro'

    # Tipo de juego
    if 'nl' in descripcion_lower or 'no limit' in descripcion_lower:
        tipo_juego = 'No Limit Hold\'em'
    elif 'pl' in descripcion_lower or 'pot limit' in descripcion_lower:
        tipo_juego = 'Pot Limit Omaha'
    elif 'limit' in descripcion_lower:
        tipo_juego = 'Limit Hold\'em'
    elif 'omaha' in descripcion_lower:
        tipo_juego = 'Omaha'
    else:
        tipo_juego = 'Hold\'em'

    return categoria, payment_method, tipo_juego


def clasificar_nivel_buyin(importe):
    """Clasifica el nivel de buy-in basado en el importe"""
    importe_abs = abs(importe)

    if importe_abs < 1:
        return 'Micro'
    elif importe_abs < 5:
        return 'Low'
    elif importe_abs < 25:
        return 'Medium'
    elif importe_abs < 100:
        return 'High'
    else:
        return 'Very High'


def procesar_archivo_wpn(filepath, user_id):
    """Procesa archivos Excel de WPN y los importa a la base de datos"""
    # Usar contexto de aplicación para las operaciones de base de datos
    with app.app_context():
        try:
            # Leer el archivo Excel
            df = pd.read_excel(filepath)
            print(f"Total registros en archivo: {len(df)}")

            # Limpiar y procesar los datos
            df_original = len(df)
            df = df.dropna(subset=['Date'])  # Eliminar filas sin fecha
            df_sin_fecha = df_original - len(df)
            print(f"Registros eliminados por falta de fecha: {df_sin_fecha}")

            # 🚀 OPTIMIZACIÓN: Obtener todos los hashes existentes en UNA sola consulta
            print("🔍 Verificando duplicados existentes...")
            hashes_existentes = set()
            existing_response = supabase.table('poker_results').select(
                'hash_duplicado').eq('user_id', user_id).execute()
            existing_records = existing_response.data if existing_response.data else []
            hashes_existentes = {record['hash_duplicado']
                for record in existing_records}
            print(
    f"✅ Encontrados {
        len(hashes_existentes)} registros existentes para comparar")

            resultados_importados = 0
            duplicados_encontrados = 0
            errores_procesamiento = 0
            duplicados_detalle = []  # Lista para almacenar detalles de duplicados

            # Crear lista de nuevos registros para insertar en lote
            nuevos_registros = []

            for index, row in df.iterrows():
                try:
                    # Procesar fecha y hora - WPN usa formato "HH:MM:SS
                    # YYYY-MM-DD"
                    fecha_str = str(row['Date'])
                    # Convertir formato "01:06:07 2025-09-24" a datetime
                    fecha_hora = pd.to_datetime(
    fecha_str, format='%H:%M:%S %Y-%m-%d')
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

                    # El tipo de movimiento se extrae directamente de Payment
                    # Method
                    tipo_movimiento = payment_method

                    # Generar hash para detectar duplicados usando campos
                    # específicos
                    hash_duplicado = generar_hash_duplicado(
                        fecha,
                        hora,
                        payment_method,
                        descripcion,
                        money_in,
                        money_out,
                        'WPN'
                    )

                    # 🚀 OPTIMIZACIÓN: Verificar duplicados en memoria (mucho más rápido)
                    if hash_duplicado in hashes_existentes:
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

                    # Agregar hash a existentes para futuras verificaciones
                    hashes_existentes.add(hash_duplicado)

                    # Calcular nivel de buy-in SOLO para registros Buy In
                    nivel_buyin = None
                    if categoria == 'Torneo' and tipo_movimiento == 'Buy In':
                        nivel_buyin = clasificar_nivel_buyin(importe)

                    # Crear nuevo registro
                    nuevo_resultado = PokerResult(
                        user_id=user_id,
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

                    nuevos_registros.append(nuevo_resultado)
                    resultados_importados += 1

                except Exception as e:
                    errores_procesamiento += 1
                    print(f"Error procesando fila {index}: {e}")
                    print(f"Datos de la fila: {row.to_dict()}")
                    continue

            # 🚀 OPTIMIZACIÓN: Insertar todos los registros en una sola operación
            if nuevos_registros:
                print(
    f"💾 Insertando {
        len(nuevos_registros)} registros en la base de datos...")
                registros_insertados = bulk_insert_poker_results(
                    user_id, nuevos_registros)
                print(
    f"✅ {registros_insertados} registros insertados exitosamente")

            print(f"Resumen del procesamiento:")
            print(f"- Registros en archivo: {df_original}")
            print(f"- Eliminados por falta de fecha: {df_sin_fecha}")
            print(f"- Errores de procesamiento: {errores_procesamiento}")
            print(f"- Duplicados omitidos: {duplicados_encontrados}")
            print(f"- Registros importados: {resultados_importados}")

            return resultados_importados, duplicados_encontrados, duplicados_detalle

        except Exception as e:
            raise Exception(f"Error procesando archivo WPN: {str(e)}")


def procesar_archivo_wpn_con_progreso_streaming(
    filepath, user_id, progress_callback):
    """Procesa archivos Excel de WPN con streaming de progreso en tiempo real"""
    # Usar contexto de aplicación para las operaciones de base de datos
    with app.app_context():
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

            # 🚀 OPTIMIZACIÓN: Obtener todos los hashes existentes en UNA sola consulta
            print("🔍 Verificando duplicados existentes...")
            hashes_existentes = set()
            existing_response = supabase.table('poker_results').select(
                'hash_duplicado').eq('user_id', user_id).execute()
            existing_records = existing_response.data if existing_response.data else []
            hashes_existentes = {record['hash_duplicado']
                for record in existing_records}
            print(
    f"✅ Encontrados {
        len(hashes_existentes)} registros existentes para comparar")

            # Enviar mensaje inicial
            yield f"data: {json.dumps({'tipo': 'inicio', 'total_registros': total_registros})}\n\n"

            resultados_importados = 0
            duplicados_encontrados = 0
            errores_procesamiento = 0
            duplicados_detalle = []

            # Crear lista de nuevos registros para insertar en lote
            nuevos_registros = []

            # Procesar todos los registros primero
            print("🔄 Procesando registros...")
            for index, row in df.iterrows():
                try:
                    # Mostrar progreso cada 100 registros
                    if (index + 1) % 100 == 0 or (index + 1) == total_registros:
                        porcentaje = ((index + 1) / total_registros) * 100
                        print(
                            f"Progreso: {index + 1}/{total_registros} registros procesados ({porcentaje:.1f}%)")

                        # Enviar progreso inmediatamente
                        progress_data = {
                            'tipo': 'progreso',
                            'procesados': index + 1,
                            'total': total_registros,
                            'porcentaje': porcentaje,
                            'etapa': 'procesando'
                        }
                        yield f"data: {json.dumps(progress_data)}\n\n"

                    # Procesar fecha y hora - WPN usa formato "HH:MM:SS
                    # YYYY-MM-DD"
                    fecha_str = str(row['Date'])
                    # Convertir formato "01:06:07 2025-09-24" a datetime
                    fecha_hora = pd.to_datetime(
    fecha_str, format='%H:%M:%S %Y-%m-%d')
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

                    # El tipo de movimiento se extrae directamente de Payment
                    # Method
                    tipo_movimiento = payment_method

                    # Generar hash para detectar duplicados usando campos
                    # específicos
                    hash_duplicado = generar_hash_duplicado(
                        fecha,
                        hora,
                        payment_method,
                        descripcion,
                        money_in,
                        money_out,
                        'WPN'
                    )

                    # 🚀 OPTIMIZACIÓN: Verificar duplicados en memoria (mucho más rápido)
                    if hash_duplicado in hashes_existentes:
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

                    # Agregar hash a existentes para futuras verificaciones
                    hashes_existentes.add(hash_duplicado)

                    # Calcular nivel de buy-in SOLO para registros Buy In
                    nivel_buyin = None
                    if categoria == 'Torneo' and tipo_movimiento == 'Buy In':
                        nivel_buyin = clasificar_nivel_buyin(importe)

                    # Crear nuevo registro
                    nuevo_resultado = PokerResult(
                        user_id=user_id,
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

                    nuevos_registros.append(nuevo_resultado)
                    resultados_importados += 1

                except Exception as e:
                    errores_procesamiento += 1
                    print(f"Error procesando fila {index}: {e}")
                    print(f"Datos de la fila: {row.to_dict()}")
                    continue

            # 🚀 OPTIMIZACIÓN: Insertar todos los registros en una sola operación
            if nuevos_registros:
                print(
    f"💾 Insertando {
        len(nuevos_registros)} registros en la base de datos...")
                registros_insertados = bulk_insert_poker_results(
                    user_id, nuevos_registros)
                print(
    f"✅ {registros_insertados} registros insertados exitosamente")

            # Enviar resultado final (sin detalles de duplicados para evitar
            # problemas de tamaño)
            resultado_final = {
                'tipo': 'completado',
                'resultados_importados': resultados_importados,
                'duplicados_encontrados': duplicados_encontrados,
                'errores_procesamiento': errores_procesamiento,
                'mensaje': f'Archivo procesado exitosamente. {resultados_importados} registros importados, {duplicados_encontrados} duplicados omitidos.',
                'duplicados_detalle_count': len(duplicados_detalle)
            }

            print(f"Resumen del procesamiento:")
            print(f"- Registros en archivo: {df_original}")
            print(f"- Eliminados por falta de fecha: {df_sin_fecha}")
            print(f"- Errores de procesamiento: {errores_procesamiento}")
            print(f"- Duplicados omitidos: {duplicados_encontrados}")
            print(f"- Registros importados: {resultados_importados}")

            # Enviar resultado principal
            # Enviar resultado principal
            yield f"data: {json.dumps(resultado_final)}\n\n"

            # Si hay duplicados, enviar detalles por separado (limitando el
            # tamaño)
            if duplicados_detalle and len(duplicados_detalle) > 0:
                # Limitar a máximo 100 detalles para evitar problemas de tamaño
                detalles_limitados = duplicados_detalle[:100]
                detalles_msg = {
                    'tipo': 'duplicados_detalle',
                    'duplicados_detalle': detalles_limitados,
                    'total_duplicados': len(duplicados_detalle),
                    'mensaje': f'Mostrando primeros 100 de {len(duplicados_detalle)} duplicados omitidos'
                }
                yield f"data: {json.dumps(detalles_msg)}\n\n"

            # Si hay duplicados, enviar detalles por separado (limitando el
            # tamaño)
            if duplicados_detalle and len(duplicados_detalle) > 0:
                # Limitar a máximo 100 detalles para evitar problemas de tamaño
                detalles_limitados = duplicados_detalle[:100]
                detalles_msg = {
                    'tipo': 'duplicados_detalle',
                    'duplicados_detalle': detalles_limitados,
                    'total_duplicados': len(duplicados_detalle),
                    'mensaje': f'Mostrando primeros 100 de {len(duplicados_detalle)} duplicados omitidos'
                }
                yield f"data: {json.dumps(detalles_msg)}\n\n"

        except Exception as e:
            error_msg = f"Error procesando archivo WPN: {str(e)}"
            print(error_msg)
            yield f"data: {json.dumps({'error': error_msg})}\n\n"


def procesar_archivo_pokerstars_con_progreso_streaming(
    filepath, user_id, progress_callback):
    """Procesa archivos HTML de Pokerstars con streaming de progreso"""
    # Usar contexto de aplicación para las operaciones de base de datos
    with app.app_context():
        try:
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
                return

            # Obtener filas
            rows = table.find_all('tr')
            if len(rows) < 3:
                error_msg = "Archivo no tiene suficientes filas"
                yield f"data: {json.dumps({'error': error_msg})}\n\n"
                return

            # Headers (segunda fila)
            subheaders = [td.get_text().strip()
                                      for td in rows[1].find_all(['td', 'th'])]

            # Filas de datos (desde la fila 2)
            data_rows = rows[2:]

            # Crear DataFrame
            data = []
            for row in data_rows:
                cells = [td.get_text().strip()
                                     for td in row.find_all(['td', 'th'])]
                if len(cells) >= len(subheaders):
                    data.append(cells[:len(subheaders)])
                else:
                    while len(cells) < len(subheaders):
                        cells.append('')
                    data.append(cells)

            if not data:
                error_msg = "No se encontraron datos en el archivo"
                yield f"data: {json.dumps({'error': error_msg})}\n\n"
                return

            df = pd.DataFrame(data, columns=subheaders)
            total_registros = len(df)

            # 🚀 OPTIMIZACIÓN: Obtener todos los hashes existentes en UNA sola consulta
            print("🔍 Verificando duplicados existentes...")
            hashes_existentes = set()
            existing_response = supabase.table('poker_results').select(
                'hash_duplicado').eq('user_id', user_id).execute()
            existing_records = existing_response.data if existing_response.data else []
            hashes_existentes = {record['hash_duplicado']
                for record in existing_records}
            print(
    f"✅ Encontrados {
        len(hashes_existentes)} registros existentes para comparar")

            # Enviar mensaje inicial
            yield f"data: {json.dumps({'tipo': 'inicio', 'total_registros': total_registros})}\n\n"

            resultados_importados = 0
            duplicados_encontrados = 0
            errores_procesamiento = 0
            duplicados_detalle = []

            # Crear lista de nuevos registros para insertar en lote
            nuevos_registros = []

            print(
    f"Procesando {total_registros} registros de Pokerstars usando DataFrame...")

            for index, row in df.iterrows():
                try:
                    # Mostrar progreso cada 100 registros
                    if (index + 1) % 100 == 0 or (index + 1) == total_registros:
                        porcentaje = ((index + 1) / total_registros) * 100
                        print(
                            f"Progreso: {index + 1}/{total_registros} registros procesados ({porcentaje:.1f}%)")

                        # Enviar progreso inmediatamente
                        progress_data = {
                            'tipo': 'progreso',
                            'procesados': index + 1,
                            'total': total_registros,
                            'porcentaje': porcentaje,
                            'etapa': 'procesando'
                        }
                        yield f"data: {json.dumps(progress_data)}\n\n"

                    # Extraer datos básicos
                    fecha_str = str(row.get('Date/Time', ''))
                    action = str(row.get('Action', ''))
                    game = str(row.get('Game', ''))
                    amount_str = str(row.get('Amount', ''))
                    tournament_id = str(
    row.get(
        'Table Name / Player / Tournament #',
         ''))

                    if not fecha_str or not action or fecha_str == 'nan' or action == 'nan':
                        errores_procesamiento += 1
                        continue

                    # Parsear fecha y hora
                    try:
                        fecha_dt = pd.to_datetime(
    fecha_str, format='%Y/%m/%d %I:%M %p')
                        fecha = fecha_dt.date()
                        hora = fecha_dt.time()
                    except Exception as e:
                        print(f"⚠️  Error procesando fecha '{fecha_str}': {e}")
                        errores_procesamiento += 1
                        continue

                    # Parsear importe
                    try:
                        amount_clean = amount_str.replace(
                            '(', '-').replace(')', '').replace(',', '').replace('$', '').strip()
                        importe = float(amount_clean)
                    except Exception as e:
                        print(
    f"⚠️  Error procesando importe '{amount_str}': {e}")
                        errores_procesamiento += 1
                        continue

                    # Categorizar movimiento
                    categoria, tipo_movimiento, tipo_juego = categorizar_movimiento_pokerstars(
                        action, game, tournament_id)

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

                    # 🚀 OPTIMIZACIÓN: Verificar duplicados en memoria (mucho más rápido)
                    if hash_duplicado in hashes_existentes:
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

                    # Agregar hash a existentes para futuras verificaciones
                    hashes_existentes.add(hash_duplicado)

                    # Crear registro
                    nuevo_resultado = PokerResult(
                        user_id=user_id,
                        fecha=fecha,
                        hora=hora,
                        tipo_movimiento=tipo_movimiento,
                        descripcion=descripcion,
                        importe=importe,
                        categoria=categoria,
                        tipo_juego=tipo_juego,
                        sala='Pokerstars',
                        hash_duplicado=hash_duplicado
                    )

                    nuevos_registros.append(nuevo_resultado)
                    resultados_importados += 1

                except Exception as e:
                    errores_procesamiento += 1
                    print(f"Error procesando fila: {e}")
                    continue

            # 🚀 OPTIMIZACIÓN: Insertar todos los registros en una sola operación
            if nuevos_registros:
                print(
    f"💾 Insertando {
        len(nuevos_registros)} registros en la base de datos...")
                registros_insertados = bulk_insert_poker_results(
                    user_id, nuevos_registros)
                print(
    f"✅ {registros_insertados} registros insertados exitosamente")

            # Enviar resultado final
            resultado_final = {
                'tipo': 'completado',
                'resultados_importados': resultados_importados,
                'duplicados_encontrados': duplicados_encontrados,
                'errores_procesamiento': errores_procesamiento,
                'mensaje': f'Archivo procesado exitosamente. {resultados_importados} registros importados, {duplicados_encontrados} duplicados omitidos.',
                'duplicados_detalle_count': len(duplicados_detalle)
            }

            print(f"Resumen del procesamiento:")
            print(f"- Errores de procesamiento: {errores_procesamiento}")
            print(f"- Duplicados omitidos: {duplicados_encontrados}")
            print(f"- Registros importados: {resultados_importados}")

            # Enviar resultado principal
            yield f"data: {json.dumps(resultado_final)}\n\n"

            # Si hay duplicados, enviar detalles por separado (limitando el
            # tamaño)
            if duplicados_detalle and len(duplicados_detalle) > 0:
                # Limitar a máximo 100 detalles para evitar problemas de tamaño
                detalles_limitados = duplicados_detalle[:100]
                detalles_msg = {
                    'tipo': 'duplicados_detalle',
                    'duplicados_detalle': detalles_limitados,
                    'total_duplicados': len(duplicados_detalle),
                    'mensaje': f'Mostrando primeros 100 de {len(duplicados_detalle)} duplicados omitidos'
                }
                yield f"data: {json.dumps(detalles_msg)}\n\n"

        except Exception as e:
            error_msg = f"Error procesando archivo Pokerstars: {str(e)}"
            print(error_msg)
            yield f"data: {json.dumps({'error': error_msg})}\n\n"


def procesar_archivo_pokerstars_excel_con_progreso_streaming(
    filepath, user_id, progress_callback):
    """Procesa archivos Excel de PokerStars con progreso en tiempo real"""
    # Usar contexto de aplicación para las operaciones de base de datos
    with app.app_context():
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
            print(f"📊 Total registros en archivo Excel: {total_registros}")

            if total_registros == 0:
                error_msg = 'No se encontraron registros en el archivo Excel'
                print(error_msg)
                yield f"data: {json.dumps({'error': error_msg})}\n\n"
                return

            # 🚀 OPTIMIZACIÓN: Obtener todos los hashes existentes en UNA sola consulta
            print("🔍 Verificando duplicados existentes...")
            hashes_existentes = set()
            existing_response = supabase.table('poker_results').select(
                'hash_duplicado').eq('user_id', user_id).execute()
            existing_records = existing_response.data if existing_response.data else []
            hashes_existentes = {record['hash_duplicado']
                for record in existing_records}
            print(
    f"✅ Encontrados {
        len(hashes_existentes)} registros existentes para comparar")

            # Enviar inicio
            yield f"data: {json.dumps({'tipo': 'inicio', 'total_registros': total_registros})}\n\n"

            resultados_importados = 0
            duplicados_encontrados = 0
            errores_procesamiento = 0
            duplicados_detalle = []

            # Crear lista de nuevos registros para insertar en lote
            nuevos_registros = []

            # Procesar cada registro
            for index, row in df.iterrows():
                try:
                    # Mostrar progreso cada 50 registros
                    if (index + 1) % 50 == 0 or (index + 1) == total_registros:
                        porcentaje = ((index + 1) / total_registros) * 100
                        print(
                            f"Progreso: {index + 1}/{total_registros} registros procesados ({porcentaje:.1f}%)")

                        # Enviar progreso
                        yield f"data: {json.dumps({'tipo': 'progreso', 'procesados': index + 1, 'total': total_registros, 'porcentaje': porcentaje, 'etapa': 'procesando'})}\n\n"

                    # Extraer datos básicos
                    fecha_str = str(row.get('Date/Time', ''))
                    action = str(row.get('Action', ''))
                    game = str(row.get('Game', ''))
                    amount_str = str(row.get('Amount', ''))
                    tournament_id = str(
    row.get(
        'Table Name / Player / Tournament #',
         ''))

                    if not fecha_str or not action or fecha_str == 'nan' or action == 'nan':
                        errores_procesamiento += 1
                        continue

                    # Parsear fecha y hora
                    try:
                        fecha_dt = pd.to_datetime(
    fecha_str, format='%Y/%m/%d %I:%M %p')
                        fecha = fecha_dt.date()
                        hora = fecha_dt.time()
                    except Exception as e:
                        print(f"⚠️  Error procesando fecha '{fecha_str}': {e}")
                        errores_procesamiento += 1
                        continue

                    # Parsear importe
                    try:
                        amount_clean = amount_str.replace(
                            '(', '-').replace(')', '').replace(',', '').replace('$', '').strip()
                        importe = float(amount_clean)
                    except Exception as e:
                        print(
    f"⚠️  Error procesando importe '{amount_str}': {e}")
                        errores_procesamiento += 1
                        continue

                    # Categorizar movimiento usando la función específica de
                    # PokerStars
                    categoria, tipo_movimiento, tipo_juego = categorizar_movimiento_pokerstars(
                        action, game, tournament_id)

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

                    # 🚀 OPTIMIZACIÓN: Verificar duplicados en memoria (mucho más rápido)
                    if hash_duplicado in hashes_existentes:
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

                    # Agregar hash a existentes para futuras verificaciones
                    hashes_existentes.add(hash_duplicado)

                    # Crear registro
                    nuevo_resultado = PokerResult(
                        user_id=user_id,
                        fecha=fecha,
                        hora=hora,
                        tipo_movimiento=tipo_movimiento,
                        descripcion=descripcion,
                        importe=importe,
                        categoria=categoria,
                        tipo_juego=tipo_juego,
                        sala='Pokerstars',
                        hash_duplicado=hash_duplicado
                    )

                    nuevos_registros.append(nuevo_resultado)
                    resultados_importados += 1

                except Exception as e:
                    errores_procesamiento += 1
                    print(f"Error procesando fila: {e}")
                    continue

            # 🚀 OPTIMIZACIÓN: Insertar todos los registros en una sola operación
            if nuevos_registros:
                print(
    f"💾 Insertando {
        len(nuevos_registros)} registros en la base de datos...")
                registros_insertados = bulk_insert_poker_results(
                    user_id, nuevos_registros)
                print(
    f"✅ {registros_insertados} registros insertados exitosamente")

            # Enviar resultado final
            resultado_final = {
                'tipo': 'completado',
                'resultados_importados': resultados_importados,
                'duplicados_encontrados': duplicados_encontrados,
                'errores_procesamiento': errores_procesamiento,
                'mensaje': f'Archivo procesado exitosamente. {resultados_importados} registros importados, {duplicados_encontrados} duplicados omitidos.',
                'duplicados_detalle_count': len(duplicados_detalle)
            }

            print(f"Resumen del procesamiento:")
            print(f"- Errores de procesamiento: {errores_procesamiento}")
            print(f"- Duplicados omitidos: {duplicados_encontrados}")
            print(f"- Registros importados: {resultados_importados}")

            # Enviar resultado principal
            yield f"data: {json.dumps(resultado_final)}\n\n"

            # Si hay duplicados, enviar detalles por separado (limitando el
            # tamaño)
            if duplicados_detalle and len(duplicados_detalle) > 0:
                # Limitar a máximo 100 detalles para evitar problemas de tamaño
                detalles_limitados = duplicados_detalle[:100]
                detalles_msg = {
                    'tipo': 'duplicados_detalle',
                    'duplicados_detalle': detalles_limitados,
                    'total_duplicados': len(duplicados_detalle),
                    'mensaje': f'Mostrando primeros 100 de {len(duplicados_detalle)} duplicados omitidos'
                }
                yield f"data: {json.dumps(detalles_msg)}\n\n"

        except Exception as e:
            error_msg = f"Error procesando archivo Pokerstars Excel: {str(e)}"
            print(error_msg)
            yield f"data: {json.dumps({'error': error_msg})}\n\n"


def procesar_archivo_pokerstars(filepath, user_id):
    """Procesa archivos HTML de Pokerstars y los importa a la base de datos"""
    # Usar contexto de aplicación para las operaciones de base de datos
    with app.app_context():
        try:
            from bs4 import BeautifulSoup

            # Leer y parsear HTML
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            soup = BeautifulSoup(content, 'html.parser')

            # Buscar tabla de transacciones
            tabla = soup.find('table', {'class': 'table'})
            if not tabla:
                raise Exception(
                    "No se encontró tabla de transacciones en el archivo HTML")

            # 🚀 OPTIMIZACIÓN: Obtener todos los hashes existentes en UNA sola consulta
            print("🔍 Verificando duplicados existentes...")
            hashes_existentes = set()
            existing_response = supabase.table('poker_results').select(
                'hash_duplicado').eq('user_id', user_id).execute()
            existing_records = existing_response.data if existing_response.data else []
            hashes_existentes = {record['hash_duplicado']
                for record in existing_records}
            print(
    f"✅ Encontrados {
        len(hashes_existentes)} registros existentes para comparar")

            resultados_importados = 0
            duplicados_encontrados = 0
            duplicados_detalle = []

            # Crear lista de nuevos registros para insertar en lote
            nuevos_registros = []

            # Procesar filas de la tabla
            filas = tabla.find_all('tr')[1:]  # Saltar encabezado

            for fila in filas:
                try:
                    celdas = fila.find_all('td')
                    if len(celdas) < 4:
                        continue

                    # Extraer datos de las celdas
                    fecha_str = celdas[0].get_text().strip()
                    tipo = celdas[1].get_text().strip()
                    descripcion = celdas[2].get_text().strip()
                    importe_str = celdas[3].get_text().strip()

                    # Procesar fecha
                    fecha = pd.to_datetime(fecha_str).date()

                    # Procesar importe
                    importe = float(
    importe_str.replace(
        '$', '').replace(
            ',', ''))

                    # Categorizar movimiento
                    categoria = 'Torneo' if 'tournament' in descripcion.lower() else 'Cash'
                    tipo_juego = 'Hold\'em'  # Por defecto

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

                    # 🚀 OPTIMIZACIÓN: Verificar duplicados en memoria (mucho más rápido)
                    if hash_duplicado in hashes_existentes:
                        duplicados_encontrados += 1
                        duplicados_detalle.append({
                            'fecha': fecha.isoformat(),
                            'tipo_movimiento': tipo,
                            'descripcion': descripcion,
                            'importe': importe,
                            'categoria': categoria,
                            'tipo_juego': tipo_juego
                        })
                        continue

                    # Agregar hash a existentes para futuras verificaciones
                    hashes_existentes.add(hash_duplicado)

                    # Crear registro
                    nuevo_resultado = PokerResult(
                        user_id=user_id,
                        fecha=fecha,
                        tipo_movimiento=tipo,
                        descripcion=descripcion,
                        importe=importe,
                        categoria=categoria,
                        tipo_juego=tipo_juego,
                        sala='Pokerstars',
                        hash_duplicado=hash_duplicado
                    )

                    nuevos_registros.append(nuevo_resultado)
                    resultados_importados += 1

                except Exception as e:
                    print(f"Error procesando fila: {e}")
                    continue

            # 🚀 OPTIMIZACIÓN: Insertar todos los registros en una sola operación
            if nuevos_registros:
                print(
    f"💾 Insertando {
        len(nuevos_registros)} registros en la base de datos...")
                registros_insertados = bulk_insert_poker_results(
                    user_id, nuevos_registros)
                print(
    f"✅ {registros_insertados} registros insertados exitosamente")

            return resultados_importados, duplicados_encontrados, duplicados_detalle

        except Exception as e:
            raise Exception(f"Error procesando archivo Pokerstars: {str(e)}")


@app.route('/api/eliminar-todos', methods=['POST'])
@login_required
def api_eliminar_todos():
    """Elimina todos los registros del usuario actual"""
    try:
        # Obtener conteo antes de eliminar usando nuestra función auxiliar
        resultados_antes = get_user_poker_results(current_user.id)
        total_registros = len(resultados_antes)

        if total_registros == 0:
            return jsonify({
                'mensaje': 'No se encontraron registros para eliminar',
                'registros_eliminados': 0
            })

        # Eliminar todos los registros del usuario usando nuestra función
        # auxiliar
        registros_eliminados = delete_user_poker_results(current_user.id)

        return jsonify({
            'mensaje': f'Se eliminaron {registros_eliminados} registros exitosamente',
            'registros_eliminados': registros_eliminados
        })

    except Exception as e:
        print(f"Error eliminando registros: {e}")
        return jsonify(
            {'error': f'Error al eliminar registros: {str(e)}'}), 500


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
        response = supabase.table('poker_results').select(
    'id',
    count='exact').eq(
        'user_id',
        current_user.id).eq(
            'sala',
             sala).execute()
        registros_sala = response.count if hasattr(
    response, 'count') else len(
        response.data) if response.data else 0

        if registros_sala == 0:
            return jsonify({
                'mensaje': f'No se encontraron registros de la sala {sala}',
                'registros_eliminados': 0
            })

        # Eliminar registros de la sala del usuario
        delete_response = supabase.table('poker_results').delete().eq(
            'user_id', current_user.id).eq('sala', sala).execute()
        registros_eliminados = len(
    delete_response.data) if delete_response.data else 0

        return jsonify({
            'mensaje': f'Se eliminaron {registros_eliminados} registros de la sala {sala}',
            'registros_eliminados': registros_eliminados,
            'sala': sala
        })

    except Exception as e:
        print(f"Error eliminando registros de sala: {e}")
        return jsonify(
            {'error': f'Error al eliminar registros de la sala: {str(e)}'}), 500


@app.route('/api/salas-disponibles', methods=['GET'])
@login_required
def api_salas_disponibles():
    """Obtiene las salas disponibles del usuario actual"""
    try:
        response = supabase.table('poker_results').select(
            'sala').eq('user_id', current_user.id).execute()
        salas_data = response.data if response.data else []
        salas = list(set([sala['sala']
                     for sala in salas_data if sala['sala']]))

        # Contar registros por sala del usuario
        salas_info = []
        for sala in salas:
            count_response = supabase.table('poker_results').select(
    'id', count='exact').eq(
        'user_id', current_user.id).eq(
            'sala', sala).execute()
            count = count_response.count if hasattr(
    count_response, 'count') else len(
        count_response.data) if count_response.data else 0
            salas_info.append({
                'sala': sala,
                'registros': count
            })

        return jsonify({
            'salas': salas_info
        })

    except Exception as e:
        print(f"Error obteniendo salas: {e}")
        return jsonify({'error': f'Error al obtener salas: {str(e)}'}), 500


@app.route('/api/informes/resultados', methods=['GET'])
@login_required
def api_informes_resultados():
    """API para obtener resultados filtrados - Multiusuario"""
    with app.app_context():
        try:
            fecha_inicio = request.args.get('fecha_inicio')
            fecha_fin = request.args.get('fecha_fin')
            tipo_movimiento = request.args.get('tipo_movimiento')
            monto_minimo = request.args.get('monto_minimo', type=float)

            # Nuevos filtros para categoría, tipo de juego, nivel de buy-in y
            # sala
            categorias = request.args.getlist('categorias[]')
            tipos_juego = request.args.getlist('tipos_juego[]')
            niveles_buyin = request.args.getlist('niveles_buyin[]')
            salas = request.args.getlist('salas[]')

            # Preparar filtros para la función auxiliar
            filters = {}
            if fecha_inicio:
                filters['fecha_inicio'] = fecha_inicio
            if fecha_fin:
                filters['fecha_fin'] = fecha_fin
            if tipo_movimiento:
                filters['tipo_movimiento'] = tipo_movimiento
            if monto_minimo is not None:
                filters['monto_minimo'] = monto_minimo
            if categorias:
                filters['categorias'] = categorias
            if tipos_juego:
                filters['tipos_juego'] = tipos_juego
            if niveles_buyin:
                filters['niveles_buyin'] = niveles_buyin
            if salas:
                filters['salas'] = salas
            if categorias:
                filters['categorias'] = categorias
            if tipos_juego:
                filters['tipos_juego'] = tipos_juego
            if niveles_buyin:
                filters['niveles_buyin'] = niveles_buyin
            if salas:
                filters['salas'] = salas

            resultados = get_user_poker_results(current_user.id, filters)

            # Calcular estadísticas
            # Contar torneos jugados: tipo_movimiento = "Buy In" y categoria =
            # "Torneo"
            cantidad_torneos = len(
                [r for r in resultados if r.tipo_movimiento == 'Buy In' and r.categoria == 'Torneo'])

            # Calcular estadísticas específicas de torneos
            torneos = [r for r in resultados if r.categoria == 'Torneo']

            # Total invertido: suma de todos los egresos (importes negativos)
            # de torneos
            total_invertido = sum(abs(r.importe)
                                  for r in torneos if r.importe < 0)

            # Total de ganancias: suma de todos los ingresos (importes
            # positivos) de torneos
            total_ganancias = sum(r.importe for r in torneos if r.importe > 0)

            # Calcular ROI: (ganancias - invertido) / invertido
            roi = 0
            if total_invertido > 0:
                roi = ((total_ganancias - total_invertido) /
                       total_invertido) * 100

            # Resultado económico excluyendo transferencias, retiros y
            # depósitos
            movimientos_poker = [
    r for r in resultados if r.categoria not in [
        'Transferencia',
        'Depósito',
         'Retiro'] and r.tipo_movimiento not in ['Retiro']]
            resultado_economico = sum(r.importe for r in movimientos_poker)

            # Suma total de todos los importes (incluyendo todos los registros
            # filtrados)
            suma_importes = sum(r.importe for r in resultados)

            # Calcular resultados diarios de los últimos 10 días (SIN FILTROS,
            # desde fecha actual)
            from datetime import timedelta

            # Obtener los últimos 10 días calendario desde HOY
            hoy = datetime.now().date()
            ultimos_10_dias = [hoy - timedelta(days=i) for i in range(10)]
            ultimos_10_dias.reverse()  # Ordenar de más antiguo a más reciente

            # Obtener TODOS los movimientos de poker del usuario (sin filtros
            # de fecha) para el gráfico
            # Obtener movimientos de poker excluyendo transferencias y retiros
            filtros_movimientos = {}
            movimientos_data = get_user_poker_results(
                current_user.id, filtros_movimientos)
            todos_movimientos_poker = [r for r in movimientos_data
                                     if r.get('categoria') not in ['Transferencia', 'Depósito']
                                     and r.get('tipo_movimiento') not in ['Retiro']]

            # Calcular resultado por día (incluir días sin datos como 0)
            resultados_diarios = []
            for fecha in ultimos_10_dias:
                # Filtrar movimientos de poker para esta fecha específica
                movimientos_dia = [
                    r for r in todos_movimientos_poker if r.fecha == fecha]
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

        except Exception as e:
            return jsonify(
                {'error': f'Error al obtener resultados: {str(e)}'}), 500

            @app.route('/api/informes/opciones', methods=['GET'])
            @login_required
def api_informes_opciones():
    """Obtiene las opciones disponibles para los filtros - Multiusuario"""
    # Usar contexto de aplicación para las operaciones de base de datos
    with app.app_context():
        try:
            # Obtener opciones únicas para el usuario actual usando funciones
            # auxiliares
            categorias = get_user_distinct_values(current_user.id, 'categoria')
            tipos_juego = get_user_distinct_values(
                current_user.id, 'tipo_juego')
            niveles_buyin = get_user_distinct_values(
                current_user.id, 'nivel_buyin')
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
            print(f"Error obteniendo opciones: {e}")
            return jsonify(
                {'success': False, 'error': f'Error al obtener opciones: {str(e)}'}), 500


@reports_ns.route('/last-10-days')
class Ultimos10Dias(Resource):
    @api.doc('get_last_10_days')
    @api.response(200, 'Resultados de últimos 10 días obtenidos exitosamente',
                  last_10_days_response_model)
    @api.response(401, 'No autenticado', error_model)
    @api.response(500, 'Error interno', error_model)
    @login_required
    def get(self):
        """Obtener resultados de los últimos 10 días sin filtros - Solo para gráfico"""
        # Usar contexto de aplicación para las operaciones de base de datos
        with app.app_context():
            try:
                from datetime import timedelta

                # Obtener los últimos 10 días calendario desde HOY
                hoy = datetime.now().date()
                ultimos_10_dias = [hoy - timedelta(days=i) for i in range(10)]
                ultimos_10_dias.reverse()  # Ordenar de más antiguo a más reciente

                # Obtener TODOS los movimientos de poker del usuario (sin
                # filtros) para el gráfico
                todos_movimientos_poker =  # Obtener datos usando Supabase
                # Obtener movimientos de poker excluyendo transferencias y
                # retiros
                filtros_movimientos = {}
                movimientos_data = get_user_poker_results(
                    current_user.id, filtros_movimientos)
                todos_movimientos_poker = [r for r in movimientos_data
                                         if r.get('categoria') not in ['Transferencia', 'Depósito']
                                         and r.get('tipo_movimiento') not in ['Retiro']]

                # Calcular resultado por día (incluir días sin datos como 0)
                resultados_diarios = []
                for fecha in ultimos_10_dias:
                    # Filtrar movimientos de poker para esta fecha específica
                    movimientos_dia = [
    r for r in todos_movimientos_poker if r.fecha == fecha]
                    resultado_dia = sum(r.importe for r in movimientos_dia)
                    resultados_diarios.append({
                        'fecha': fecha.isoformat(),
                        'resultado': float(resultado_dia),
                        'movimientos': len(movimientos_dia)
                    })

                return {
                    'resultados_diarios': resultados_diarios,
                    'total_dias': 10,
                    'fecha_inicio': ultimos_10_dias[0].isoformat(),
                    'fecha_fin': ultimos_10_dias[-1].isoformat()
                }

            except Exception as e:
                return {
                    'error': f'Error al obtener resultados de últimos 10 días: {str(e)}'}, 500


@app.route('/api/debug/test', methods=['GET'])
def api_debug_test():
    """Endpoint de prueba para debug"""
    return jsonify({
        'mensaje': 'Endpoint de prueba funcionando',
        'timestamp': datetime.now().isoformat(),
        'status': 'ok'
    })


@app.route('/api/informes/ultimos-10-dias', methods=['GET'])
@login_required
def api_ultimos_10_dias():
    """Obtener resultados de los últimos 10 días sin filtros - Solo para gráfico"""
    # Usar contexto de aplicación para las operaciones de base de datos
    with app.app_context():
        try:
            from datetime import timedelta

            # Obtener los últimos 10 días calendario desde HOY
            hoy = datetime.now().date()
            ultimos_10_dias = [hoy - timedelta(days=i) for i in range(10)]
            ultimos_10_dias.reverse()  # Ordenar de más antiguo a más reciente

            # Obtener TODOS los movimientos de poker del usuario (sin filtros)
            # para el gráfico
            todos_movimientos_poker =  # Obtener datos usando Supabase
            # Obtener movimientos de poker excluyendo transferencias y retiros
            filtros_movimientos = {}
            movimientos_data = get_user_poker_results(
                current_user.id, filtros_movimientos)
            todos_movimientos_poker = [r for r in movimientos_data
                                     if r.get('categoria') not in ['Transferencia', 'Depósito']
                                     and r.get('tipo_movimiento') not in ['Retiro']]

            # Calcular resultado por día (incluir días sin datos como 0)
            resultados_diarios = []
            for fecha in ultimos_10_dias:
                # Filtrar movimientos de poker para esta fecha específica
                movimientos_dia = [
    r for r in todos_movimientos_poker if r.fecha == fecha]
                resultado_dia = sum(r.importe for r in movimientos_dia)
                resultados_diarios.append({
                    'fecha': fecha.isoformat(),
                    'resultado': float(resultado_dia),
                    'movimientos': len(movimientos_dia)
                })

            return jsonify({
                'resultados_diarios': resultados_diarios,
                'total_dias': 10,
                'fecha_inicio': ultimos_10_dias[0].isoformat(),
                'fecha_fin': ultimos_10_dias[-1].isoformat()
            })

        except Exception as e:
            return jsonify(
                {'error': f'Error al obtener resultados de últimos 10 días: {str(e)}'}), 500


@app.route('/api/analisis/insights', methods=['GET'])
@login_required
def api_analisis_insights():
    """Análisis avanzado con insights para gestión del juego"""
    # Usar contexto de aplicación para las operaciones de base de datos
    with app.app_context():
        try:
            # Obtener todos los registros de torneos del usuario actual
            torneos =  # Obtener datos usando Supabase
            # Obtener torneos del usuario
            filtros_torneos = {'categorias': ['Torneo']}
            torneos_data = get_user_poker_results(
                current_user.id, filtros_torneos)
            torneos = torneos_data

            if not torneos:
                return jsonify({
                    'success': True,
                    'message': 'No hay datos de torneos para analizar',
                    'analisis_buyin': {},
                    'analisis_sala': {},
                    'analisis_temporal': {},
                    'analisis_juego': {},
                    'analisis_consistencia': {},
                    'recomendaciones': []
                })

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
            recomendaciones = generar_recomendaciones(
    analisis_buyin, analisis_temporal, analisis_juego, analisis_consistencia)

            return jsonify({
                'success': True,
                'analisis_buyin': analisis_buyin,
                'analisis_sala': analisis_sala,
                'analisis_temporal': analisis_temporal,
                'analisis_juego': analisis_juego,
                'analisis_consistencia': analisis_consistencia,
                'recomendaciones': recomendaciones
            })

        except Exception as e:
            return jsonify(
                {'success': False, 'error': f'Error en análisis: {str(e)}'}), 500


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
            buyin_stats[torneo.nivel_buyin]['total_invertido'] += abs(
                torneo.importe) if torneo.importe < 0 else 0
            buyin_stats[torneo.nivel_buyin]['total_ganancias'] += torneo.importe if torneo.importe > 0 else 0
            buyin_stats[torneo.nivel_buyin]['salas'].add(torneo.sala)

    # Calcular ROI y rachas
    for nivel, stats in buyin_stats.items():
        if stats['total_invertido'] > 0:
            stats['roi'] = (
    (stats['total_ganancias'] - stats['total_invertido']) / stats['total_invertido']) * 100

        # Calcular rachas (simplificado)
        stats['mejor_racha'] = max(
    0,
    stats['total_ganancias'] /
     stats['total_invertido'] if stats['total_invertido'] > 0 else 0)
        stats['peor_racha'] = min(
    0,
    (stats['total_ganancias'] -
    stats['total_invertido']) /
     stats['total_invertido'] if stats['total_invertido'] > 0 else 0)

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
            sala_stats[torneo.sala]['total_invertido'] += abs(
                torneo.importe) if torneo.importe < 0 else 0
            sala_stats[torneo.sala]['total_ganancias'] += torneo.importe if torneo.importe > 0 else 0

            if torneo.importe > 0:
                sala_stats[torneo.sala]['torneos_ganados'] += 1

            if torneo.tipo_juego:
                sala_stats[torneo.sala]['tipos_juego'].add(torneo.tipo_juego)

            if torneo.nivel_buyin:
                sala_stats[torneo.sala]['niveles_buyin'].add(
                    torneo.nivel_buyin)

    # Calcular ROI y porcentaje de victorias
    for sala, stats in sala_stats.items():
        if stats['total_invertido'] > 0:
            stats['roi'] = (
    (stats['total_ganancias'] - stats['total_invertido']) / stats['total_invertido']) * 100

        if stats['total_torneos'] > 0:
            stats['porcentaje_victorias'] = (
    stats['torneos_ganados'] / stats['total_torneos']) * 100

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
    dias_nombres = [
    'Lunes',
    'Martes',
    'Miércoles',
    'Jueves',
    'Viernes',
    'Sábado',
     'Domingo']

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
            juego_stats[torneo.tipo_juego]['total_invertido'] += abs(
                torneo.importe) if torneo.importe < 0 else 0
            juego_stats[torneo.tipo_juego]['total_ganancias'] += torneo.importe if torneo.importe > 0 else 0

            if torneo.importe > 0:
                juego_stats[torneo.tipo_juego]['torneos_ganados'] += 1

    # Calcular ROI y porcentaje de victorias
    for juego, stats in juego_stats.items():
        if stats['total_invertido'] > 0:
            stats['roi'] = (
    (stats['total_ganancias'] - stats['total_invertido']) / stats['total_invertido']) * 100

        if stats['total_torneos'] > 0:
            stats['porcentaje_victorias'] = (
    stats['torneos_ganados'] / stats['total_torneos']) * 100

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

            if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)

