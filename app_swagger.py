#!/usr/bin/env python3
"""
Aplicación de análisis de resultados de poker - Versión Multiusuario con Swagger
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
import uuid
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SelectField, SubmitField, DateField, IntegerField
from wtforms.validators import DataRequired, Length, Email, EqualTo
from dotenv import load_dotenv

# Importar Flask-RESTX para Swagger
from flask_restx import Api, Resource, fields, Namespace

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Configuración de base de datos - Solo PostgreSQL
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("DATABASE_URL no está configurado. Se requiere PostgreSQL para esta aplicación.")

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
print("🔗 Conectando a PostgreSQL...")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configurar Swagger/OpenAPI
app.config['RESTX_MASK_SWAGGER'] = False
app.config['SWAGGER_UI_DOC_EXPANSION'] = 'list'
app.config['SWAGGER_UI_OPERATION_ID'] = True
app.config['SWAGGER_UI_REQUEST_DURATION'] = True

# Configuración de archivos
UPLOAD_FOLDER = 'uploads'
PROCESADOS_FOLDER = 'procesados'
ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'html'}

# Crear carpetas si no existen
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESADOS_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESADOS_FOLDER'] = PROCESADOS_FOLDER

# Inicializar extensiones
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Configurar API con Swagger
api = Api(
    app,
    version='1.0',
    title='Poker Results API',
    description='API para análisis y gestión de resultados de poker',
    doc='/swagger/',
    authorizations={
        'Bearer': {
            'type': 'apiKey',
            'in': 'header',
            'name': 'Authorization',
            'description': 'Token de autenticación (Bearer token)'
        }
    },
    security=['Bearer']
)

# Definir namespaces para organizar endpoints
auth_ns = Namespace('auth', description='Autenticación y gestión de usuarios')
import_ns = Namespace('import', description='Importación de archivos')
reports_ns = Namespace('reports', description='Informes y estadísticas')
analysis_ns = Namespace('analysis', description='Análisis avanzado')
admin_ns = Namespace('admin', description='Funciones administrativas')

api.add_namespace(auth_ns, path='/api/auth')
api.add_namespace(import_ns, path='/api/import')
api.add_namespace(reports_ns, path='/api/reports')
api.add_namespace(analysis_ns, path='/api/analysis')
api.add_namespace(admin_ns, path='/api/admin')

# =============================================================================
# MODELOS DE DATOS PARA SWAGGER
# =============================================================================

# Modelos de respuesta
poker_result_model = api.model('PokerResult', {
    'id': fields.Integer(description='ID del resultado'),
    'fecha': fields.String(description='Fecha del resultado (YYYY-MM-DD)'),
    'hora': fields.String(description='Hora del resultado (HH:MM:SS)'),
    'tipo_movimiento': fields.String(description='Tipo de movimiento'),
    'descripcion': fields.String(description='Descripción del movimiento'),
    'importe': fields.Float(description='Importe del movimiento'),
    'categoria': fields.String(description='Categoría del movimiento'),
    'tipo_juego': fields.String(description='Tipo de juego'),
    'nivel_buyin': fields.String(description='Nivel de buy-in'),
    'sala': fields.String(description='Sala de poker')
})

estadisticas_model = api.model('Estadisticas', {
    'cantidad_torneos': fields.Integer(description='Cantidad de torneos'),
    'total_registros': fields.Integer(description='Total de registros'),
    'suma_importes': fields.Float(description='Suma total de importes'),
    'total_invertido': fields.Float(description='Total invertido'),
    'total_ganancias': fields.Float(description='Total de ganancias'),
    'roi': fields.Float(description='Retorno de inversión (%)'),
    'resultado_economico': fields.Float(description='Resultado económico')
})

resultado_diario_model = api.model('ResultadoDiario', {
    'fecha': fields.String(description='Fecha (YYYY-MM-DD)'),
    'resultado': fields.Float(description='Resultado del día'),
    'movimientos': fields.Integer(description='Cantidad de movimientos')
})

informes_response_model = api.model('InformesResponse', {
    'resultados': fields.List(fields.Nested(poker_result_model), description='Lista de resultados'),
    'estadisticas': fields.Nested(estadisticas_model, description='Estadísticas calculadas'),
    'resultados_diarios': fields.List(fields.Nested(resultado_diario_model), description='Resultados de últimos 10 días')
})

opciones_model = api.model('OpcionesFiltros', {
    'categorias': fields.List(fields.String, description='Categorías disponibles'),
    'tipos_juego': fields.List(fields.String, description='Tipos de juego disponibles'),
    'niveles_buyin': fields.List(fields.String, description='Niveles de buy-in disponibles'),
    'salas': fields.List(fields.String, description='Salas disponibles')
})

# Modelo para respuesta de últimos 10 días
last_10_days_response_model = api.model('Last10DaysResponse', {
    'resultados_diarios': fields.List(fields.Nested(resultado_diario_model), description='Resultados de últimos 10 días'),
    'total_dias': fields.Integer(description='Total de días (siempre 10)'),
    'fecha_inicio': fields.String(description='Fecha de inicio del período'),
    'fecha_fin': fields.String(description='Fecha de fin del período')
})

import_response_model = api.model('ImportResponse', {
    'mensaje': fields.String(description='Mensaje de resultado'),
    'resultados_importados': fields.Integer(description='Cantidad de registros importados'),
    'duplicados_encontrados': fields.Integer(description='Cantidad de duplicados encontrados'),
    'duplicados_detalle': fields.List(fields.Raw, description='Detalle de duplicados')
})

salas_info_model = api.model('SalaInfo', {
    'sala': fields.String(description='Nombre de la sala'),
    'registros': fields.Integer(description='Cantidad de registros')
})

error_model = api.model('Error', {
    'error': fields.String(description='Mensaje de error')
})

# Modelos de request
filtros_informes_parser = api.parser()
filtros_informes_parser.add_argument('fecha_inicio', type=str, help='Fecha de inicio (YYYY-MM-DD)')
filtros_informes_parser.add_argument('fecha_fin', type=str, help='Fecha de fin (YYYY-MM-DD)')
filtros_informes_parser.add_argument('tipo_movimiento', type=str, help='Tipo de movimiento')
filtros_informes_parser.add_argument('monto_minimo', type=float, help='Monto mínimo')
filtros_informes_parser.add_argument('categorias', type=str, action='append', help='Categorías (múltiples)')
filtros_informes_parser.add_argument('tipos_juego', type=str, action='append', help='Tipos de juego (múltiples)')
filtros_informes_parser.add_argument('niveles_buyin', type=str, action='append', help='Niveles de buy-in (múltiples)')
filtros_informes_parser.add_argument('salas', type=str, action='append', help='Salas (múltiples)')

eliminar_sala_parser = api.parser()
eliminar_sala_parser.add_argument('sala', type=str, required=True, help='Nombre de la sala a eliminar')

# =============================================================================
# MODELOS DE BASE DE DATOS (igual que en app_multiusuario.py)
# =============================================================================

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Relación con resultados
    poker_results = db.relationship('PokerResult', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class PokerResult(db.Model):
    __tablename__ = 'poker_results'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    hora = db.Column(db.Time)
    tipo_movimiento = db.Column(db.String(50), nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    importe = db.Column(db.Numeric(10, 2), nullable=False)
    categoria = db.Column(db.String(50), nullable=False)
    tipo_juego = db.Column(db.String(50), nullable=False)
    nivel_buyin = db.Column(db.String(50))
    sala = db.Column(db.String(50), nullable=False)
    hash_duplicado = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    """Cargar usuario - Solo PostgreSQL con UUIDs"""
    if not user_id:
        return None
    
    try:
        return User.query.get(str(user_id))
    except Exception as e:
        print(f"❌ Error cargando usuario {user_id}: {e}")
        return None

# =============================================================================
# FORMULARIOS (igual que en app_multiusuario.py)
# =============================================================================

class LoginForm(FlaskForm):
    username = StringField('Nombre de usuario', validators=[DataRequired(), Length(min=4, max=20)])
    password = PasswordField('Contraseña', validators=[DataRequired()])
    remember_me = BooleanField('Recordarme')
    submit = SubmitField('Iniciar sesión')

class RegistrationForm(FlaskForm):
    username = StringField('Nombre de usuario', validators=[DataRequired(), Length(min=4, max=20)])
    email = StringField('Correo electrónico', validators=[DataRequired(), Email()])
    password = PasswordField('Contraseña', validators=[DataRequired(), Length(min=6)])
    password2 = PasswordField('Repetir contraseña', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Registrarse')

class AdminAnalysisForm(FlaskForm):
    user_id = SelectField('Usuario', coerce=int, validators=[DataRequired()])
    fecha_inicio = DateField('Fecha de inicio')
    fecha_fin = DateField('Fecha de fin')
    tipo_analisis = SelectField('Tipo de análisis', choices=[
        ('general', 'Análisis general'),
        ('buyin', 'Por nivel de buy-in'),
        ('sala', 'Por sala'),
        ('temporal', 'Temporal'),
        ('juego', 'Por tipo de juego')
    ])
    submit = SubmitField('Generar análisis')

# =============================================================================
# FUNCIONES AUXILIARES (igual que en app_multiusuario.py)
# =============================================================================

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# =============================================================================
# RUTAS TRADICIONALES (PÁGINAS WEB)
# =============================================================================

@app.route('/')
def index():
    """Página principal"""
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        flash('Usuario o contraseña incorrectos')
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        # Verificar si el usuario ya existe
        if User.query.filter_by(username=form.username.data).first():
            flash('El nombre de usuario ya está en uso')
            return render_template('register.html', form=form)
        
        if User.query.filter_by(email=form.email.data).first():
            flash('El correo electrónico ya está registrado')
            return render_template('register.html', form=form)
        
        # Crear nuevo usuario
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        
        # Si es el primer usuario, hacerlo admin
        if User.query.count() == 0:
            user.is_admin = True
        
        db.session.add(user)
        db.session.commit()
        
        flash('Registro exitoso. Ahora puedes iniciar sesión.')
        return redirect(url_for('login'))
    
    return render_template('register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

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

@app.route('/admin')
@login_required
def admin():
    """Panel de administración"""
    if not current_user.is_admin:
        flash('Acceso denegado. Se requieren privilegios de administrador.')
        return redirect(url_for('index'))
    
    users = User.query.all()
    stats = {}
    for user in users:
        user_results = PokerResult.query.filter_by(user_id=user.id).count()
        stats[user.id] = user_results
    
    return render_template('admin.html', users=users, stats=stats)

@app.route('/admin/analisis')
@login_required
def admin_analisis():
    """Análisis administrativo"""
    if not current_user.is_admin:
        flash('Acceso denegado. Se requieren privilegios de administrador.')
        return redirect(url_for('index'))
    
    form = AdminAnalysisForm()
    form.user_id.choices = [(user.id, f"{user.username} ({user.email})") for user in User.query.all()]
    
    return render_template('admin_analisis.html', form=form)

# =============================================================================
# FUNCIONES DE AUTENTICACIÓN
# =============================================================================

def authenticate_bearer_token():
    """Autenticar usando Bearer token"""
    auth_header = request.headers.get('Authorization')
    
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    
    token = auth_header.split(' ')[1]
    
    # Para desarrollo/testing, permitir cualquier token válido
    # En producción, implementar validación de token contra base de datos
    # Por ahora, devolver el primer usuario disponible
    user = User.query.first()
    if user:
        return user
    
    return None

def require_auth(f):
    """Decorador para requerir autenticación Bearer o sesión"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Intentar autenticación Bearer primero
        user = authenticate_bearer_token()
        
        if user:
            # Usar el usuario autenticado
            from flask_login import login_user
            login_user(user)
            return f(*args, **kwargs)
        
        # Si no hay Bearer token, verificar sesión web
        if current_user.is_authenticated:
            return f(*args, **kwargs)
        
        # Si no hay autenticación, devolver error 401
        from flask import jsonify
        return jsonify({'error': 'Token de autenticación requerido'}), 401
    
    return decorated_function

# =============================================================================
# API ENDPOINTS CON SWAGGER
# =============================================================================

# Modelo para el login
login_model = api.model('LoginRequest', {
    'username': fields.String(required=True, description='Nombre de usuario'),
    'password': fields.String(required=True, description='Contraseña')
})

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
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            # Generar un token simple para la sesión
            import secrets
            token = secrets.token_urlsafe(32)
            session['api_token'] = token
            
            return {
                'mensaje': 'Login exitoso',
                'token': token,
                'user_id': user.id,
                'username': user.username
            }, 200
        else:
            return {'error': 'Credenciales inválidas'}, 401

@auth_ns.route('/token')
class GetToken(Resource):
    @api.doc('get_current_token')
    @api.response(200, 'Token obtenido exitosamente')
    @api.response(401, 'No autenticado', error_model)
    @require_auth
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
    @require_auth
    def post(self):
        """Cerrar sesión de usuario"""
        session.pop('api_token', None)
        logout_user()
        return {'mensaje': 'Logout exitoso'}, 200

@import_ns.route('/upload')
class ImportUpload(Resource):
    @api.doc('upload_file')
    @api.expect(api.parser().add_argument('archivo', location='files', type='file', required=True, help='Archivo a importar'))
    @api.response(200, 'Importación exitosa', import_response_model)
    @api.response(400, 'Error en el archivo', error_model)
    @api.response(500, 'Error interno', error_model)
    @require_auth
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
    @require_auth
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
    @require_auth
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
                'ultima_importacion': ultimo_registro.fecha.isoformat() if ultimo_registro else None,
                'usuario': current_user.username
            }
            
            return estadisticas
            
        except Exception as e:
            return {'error': f'Error al obtener estado: {str(e)}'}, 500


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
    @api.response(200, 'Resultados obtenidos exitosamente', informes_response_model)
    @api.response(401, 'No autenticado', error_model)
    @api.response(500, 'Error interno', error_model)
    @require_auth
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
            query = PokerResult.query.filter_by(user_id=current_user.id)
            
            # Aplicar filtros
            if categoria:
                query = query.filter(PokerResult.categoria == categoria)
            if tipo_juego:
                query = query.filter(PokerResult.tipo_juego == tipo_juego)
            if nivel_buyin:
                query = query.filter(PokerResult.nivel_buyin == nivel_buyin)
            if sala:
                query = query.filter(PokerResult.sala == sala)
            if fecha_inicio:
                query = query.filter(PokerResult.fecha >= datetime.strptime(fecha_inicio, '%Y-%m-%d').date())
            if fecha_fin:
                query = query.filter(PokerResult.fecha <= datetime.strptime(fecha_fin, '%Y-%m-%d').date())
            
            # Obtener resultados paginados
            resultados = query.order_by(PokerResult.fecha.desc(), PokerResult.hora.desc()).paginate(
                page=page, per_page=per_page, error_out=False
            )
            
            # Calcular estadísticas
            total_registros = query.count()
            suma_importes = query.with_entities(db.func.sum(PokerResult.importe)).scalar() or 0
            
            # Calcular estadísticas de torneos
            torneos_query = query.filter(PokerResult.categoria == 'Torneo')
            cantidad_torneos = torneos_query.count()
            
            # Calcular total invertido y ganancias
            total_invertido = query.filter(PokerResult.importe < 0).with_entities(
                db.func.sum(db.func.abs(PokerResult.importe))
            ).scalar() or 0
            
            total_ganancias = query.filter(PokerResult.importe > 0).with_entities(
                db.func.sum(PokerResult.importe)
            ).scalar() or 0
            
            # Calcular ROI
            roi = (total_ganancias / total_invertido * 100) if total_invertido > 0 else 0
            resultado_economico = total_ganancias - total_invertido
            
            # Calcular resultados diarios de los últimos 10 días (SIN FILTROS, desde fecha actual)
            from datetime import timedelta
            hoy = datetime.now().date()
            ultimos_10_dias = [hoy - timedelta(days=i) for i in range(10)]
            ultimos_10_dias.reverse()
            
            # Obtener todos los movimientos de poker (sin filtros) para el gráfico
            todos_movimientos_poker = PokerResult.query.filter(
                PokerResult.user_id == current_user.id,
                PokerResult.categoria.notin_(['Transferencia', 'Depósito']),
                PokerResult.tipo_movimiento.notin_(['Retiro'])
            ).all()
            
            resultados_diarios = []
            for fecha in ultimos_10_dias:
                movimientos_dia = [r for r in todos_movimientos_poker if r.fecha == fecha]
                resultado_dia = sum(r.importe for r in movimientos_dia)
                resultados_diarios.append({
                    'fecha': fecha.isoformat(),
                    'resultado': resultado_dia,
                    'movimientos': len(movimientos_dia)
                })
            
            # Formatear resultados
            resultados_formateados = []
            for resultado in resultados.items:
                resultados_formateados.append({
                    'fecha': resultado.fecha.isoformat(),
                    'hora': resultado.hora.strftime('%H:%M:%S'),
                    'tipo_movimiento': resultado.tipo_movimiento,
                    'descripcion': resultado.descripcion,
                    'importe': float(resultado.importe),
                    'categoria': resultado.categoria,
                    'tipo_juego': resultado.tipo_juego,
                    'nivel_buyin': resultado.nivel_buyin,
                    'sala': resultado.sala
                })
            
            return {
                'resultados': {
                    'registros': resultados_formateados,
                    'paginacion': {
                        'pagina_actual': resultados.page,
                        'total_paginas': resultados.pages,
                        'total_registros': resultados.total,
                        'por_pagina': per_page
                    }
                },
                'estadisticas': {
                    'cantidad_torneos': cantidad_torneos,
                    'total_registros': total_registros,
                    'suma_importes': float(suma_importes),
                    'total_invertido': float(total_invertido),
                    'total_ganancias': float(total_ganancias),
                    'roi': round(roi, 2),
                    'resultado_economico': float(resultado_economico)
                },
                'resultados_diarios': resultados_diarios
            }
            
        except Exception as e:
            return {'error': f'Error al obtener resultados: {str(e)}'}, 500

@reports_ns.route('/options')
class InformesOpciones(Resource):
    @api.doc('get_filter_options')
    @api.response(200, 'Opciones obtenidas exitosamente', opciones_model)
    @api.response(401, 'No autenticado', error_model)
    @api.response(500, 'Error interno', error_model)
    @require_auth
    def get(self):
        """Obtener opciones disponibles para filtros"""
        try:
            # Obtener opciones únicas para el usuario actual
            categorias = db.session.query(PokerResult.categoria).filter_by(user_id=current_user.id).distinct().all()
            tipos_juego = db.session.query(PokerResult.tipo_juego).filter_by(user_id=current_user.id).distinct().all()
            niveles_buyin = db.session.query(PokerResult.nivel_buyin).filter_by(user_id=current_user.id).distinct().all()
            salas = db.session.query(PokerResult.sala).filter_by(user_id=current_user.id).distinct().all()
            
            return {
                'categorias': [c[0] for c in categorias if c[0]],
                'tipos_juego': [t[0] for t in tipos_juego if t[0]],
                'niveles_buyin': [n[0] for n in niveles_buyin if n[0]],
                'salas': [s[0] for s in salas if s[0]]
            }
            
        except Exception as e:
            return {'error': f'Error al obtener opciones: {str(e)}'}, 500

@reports_ns.route('/last-10-days')
class Ultimos10Dias(Resource):
    @api.doc('get_last_10_days')
    @api.response(200, 'Resultados de últimos 10 días obtenidos exitosamente', last_10_days_response_model)
    @api.response(401, 'No autenticado', error_model)
    @api.response(500, 'Error interno', error_model)
    @login_required
    def get(self):
        """Obtener resultados de los últimos 10 días sin filtros - Solo para gráfico"""
        try:
            from datetime import timedelta
            
            # Obtener los últimos 10 días calendario desde HOY
            hoy = datetime.now().date()
            ultimos_10_dias = [hoy - timedelta(days=i) for i in range(10)]
            ultimos_10_dias.reverse()  # Ordenar de más antiguo a más reciente
            
            # Obtener TODOS los movimientos de poker del usuario (sin filtros) para el gráfico
            todos_movimientos_poker = PokerResult.query.filter(
                PokerResult.user_id == current_user.id,
                PokerResult.categoria.notin_(['Transferencia', 'Depósito']),
                PokerResult.tipo_movimiento.notin_(['Retiro'])
            ).all()
            
            # Calcular resultado por día (incluir días sin datos como 0)
            resultados_diarios = []
            for fecha in ultimos_10_dias:
                # Filtrar movimientos de poker para esta fecha específica
                movimientos_dia = [r for r in todos_movimientos_poker if r.fecha == fecha]
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
            return {'error': f'Error al obtener resultados de últimos 10 días: {str(e)}'}, 500

@admin_ns.route('/delete-all')
class EliminarTodos(Resource):
    @api.doc('delete_all_records')
    @api.response(200, 'Registros eliminados exitosamente')
    @api.response(500, 'Error interno', error_model)
    @require_auth
    def post(self):
        """Eliminar todos los registros del usuario actual"""
        try:
            # Contar registros del usuario antes de eliminar
            total_registros = PokerResult.query.filter_by(user_id=current_user.id).count()
            
            if total_registros == 0:
                return {
                    'mensaje': 'No se encontraron registros para eliminar',
                    'registros_eliminados': 0
                }
            
            # Eliminar todos los registros del usuario
            PokerResult.query.filter_by(user_id=current_user.id).delete()
            db.session.commit()
            
            return {
                'mensaje': f'Se eliminaron {total_registros} registros exitosamente',
                'registros_eliminados': total_registros
            }
            
        except Exception as e:
            db.session.rollback()
            return {'error': f'Error al eliminar registros: {str(e)}'}, 500

@admin_ns.route('/delete-by-room')
class EliminarPorSala(Resource):
    @api.doc('delete_records_by_room')
    @api.expect(eliminar_sala_parser)
    @api.response(200, 'Registros eliminados exitosamente')
    @api.response(400, 'Sala no encontrada', error_model)
    @api.response(500, 'Error interno', error_model)
    @require_auth
    def post(self):
        """Eliminar registros de una sala específica del usuario actual"""
        args = eliminar_sala_parser.parse_args()
        sala = args['sala']
        
        try:
            # Contar registros de la sala antes de eliminar
            total_registros = PokerResult.query.filter_by(user_id=current_user.id, sala=sala).count()
            
            if total_registros == 0:
                return {'error': f'No se encontraron registros para la sala: {sala}'}, 400
            
            # Eliminar registros de la sala específica
            PokerResult.query.filter_by(user_id=current_user.id, sala=sala).delete()
            db.session.commit()
            
            return {
                'mensaje': f'Se eliminaron {total_registros} registros de la sala {sala} exitosamente',
                'registros_eliminados': total_registros,
                'sala': sala
            }
            
        except Exception as e:
            db.session.rollback()
            return {'error': f'Error al eliminar registros de la sala: {str(e)}'}, 500

@admin_ns.route('/available-rooms')
class SalasDisponibles(Resource):
    @api.doc('get_available_rooms')
    @api.response(200, 'Salas obtenidas exitosamente')
    @api.response(500, 'Error interno', error_model)
    @require_auth
    def get(self):
        """Obtener las salas disponibles del usuario actual"""
        try:
            salas = db.session.query(PokerResult.sala).filter_by(user_id=current_user.id).distinct().all()
            salas = [sala[0] for sala in salas if sala[0]]
            
            # Contar registros por sala del usuario
            salas_info = []
            for sala in salas:
                count = PokerResult.query.filter_by(user_id=current_user.id, sala=sala).count()
                salas_info.append({
                    'sala': sala,
                    'registros': count
                })
            
            return {'salas': salas_info}
            
        except Exception as e:
            return {'error': f'Error al obtener salas: {str(e)}'}, 500

@admin_ns.route('/stats')
class AdminStats(Resource):
    @api.doc('get_admin_stats')
    @api.response(200, 'Estadísticas obtenidas exitosamente')
    @api.response(401, 'No autenticado', error_model)
    @api.response(500, 'Error interno', error_model)
    @require_auth
    def get(self):
        """Obtener estadísticas generales del usuario"""
        try:
            # Estadísticas básicas
            total_registros = PokerResult.query.filter_by(user_id=current_user.id).count()
            total_torneos = PokerResult.query.filter_by(user_id=current_user.id, categoria='Torneo').count()
            
            # Estadísticas por sala
            salas_stats = db.session.query(
                PokerResult.sala,
                db.func.count(PokerResult.id).label('registros'),
                db.func.sum(PokerResult.importe).label('total_importe')
            ).filter_by(user_id=current_user.id).group_by(PokerResult.sala).all()
            
            # Estadísticas por categoría
            categorias_stats = db.session.query(
                PokerResult.categoria,
                db.func.count(PokerResult.id).label('registros'),
                db.func.sum(PokerResult.importe).label('total_importe')
            ).filter_by(user_id=current_user.id).group_by(PokerResult.categoria).all()
            
            # Rango de fechas
            fecha_min = db.session.query(db.func.min(PokerResult.fecha)).filter_by(user_id=current_user.id).scalar()
            fecha_max = db.session.query(db.func.max(PokerResult.fecha)).filter_by(user_id=current_user.id).scalar()
            
            return {
                'usuario': current_user.username,
                'total_registros': total_registros,
                'total_torneos': total_torneos,
                'rango_fechas': {
                    'inicio': fecha_min.isoformat() if fecha_min else None,
                    'fin': fecha_max.isoformat() if fecha_max else None
                },
                'estadisticas_por_sala': [
                    {
                        'sala': stat.sala,
                        'registros': stat.registros,
                        'total_importe': float(stat.total_importe or 0)
                    } for stat in salas_stats
                ],
                'estadisticas_por_categoria': [
                    {
                        'categoria': stat.categoria,
                        'registros': stat.registros,
                        'total_importe': float(stat.total_importe or 0)
                    } for stat in categorias_stats
                ]
            }
            
        except Exception as e:
            return {'error': f'Error al obtener estadísticas: {str(e)}'}, 500

@admin_ns.route('/users')
class AdminUsers(Resource):
    @api.doc('get_all_users')
    @api.response(200, 'Usuarios obtenidos exitosamente')
    @api.response(401, 'No autenticado', error_model)
    @api.response(403, 'Acceso denegado', error_model)
    @api.response(500, 'Error interno', error_model)
    @require_auth
    def get(self):
        """Obtener lista de todos los usuarios (solo admin)"""
        try:
            if not current_user.is_admin:
                return {'error': 'Acceso denegado. Se requieren permisos de administrador'}, 403
            
            usuarios = User.query.all()
            usuarios_info = []
            
            for usuario in usuarios:
                total_registros = PokerResult.query.filter_by(user_id=usuario.id).count()
                usuarios_info.append({
                    'id': usuario.id,
                    'username': usuario.username,
                    'email': usuario.email,
                    'is_admin': usuario.is_admin,
                    'total_registros': total_registros,
                    'fecha_registro': usuario.created_at.isoformat() if hasattr(usuario, 'created_at') else None
                })
            
            return {'usuarios': usuarios_info}
            
        except Exception as e:
            return {'error': f'Error al obtener usuarios: {str(e)}'}, 500

@admin_ns.route('/backup')
class AdminBackup(Resource):
    @api.doc('create_backup')
    @api.response(200, 'Backup creado exitosamente')
    @api.response(401, 'No autenticado', error_model)
    @api.response(500, 'Error interno', error_model)
    @require_auth
    def post(self):
        """Crear backup de los datos del usuario"""
        try:
            # Obtener todos los registros del usuario
            registros = PokerResult.query.filter_by(user_id=current_user.id).all()
            
            # Crear backup en formato JSON
            backup_data = {
                'usuario': current_user.username,
                'fecha_backup': datetime.now().isoformat(),
                'total_registros': len(registros),
                'registros': []
            }
            
            for registro in registros:
                backup_data['registros'].append({
                    'fecha': registro.fecha.isoformat(),
                    'hora': registro.hora.strftime('%H:%M:%S'),
                    'tipo_movimiento': registro.tipo_movimiento,
                    'descripcion': registro.descripcion,
                    'importe': float(registro.importe),
                    'categoria': registro.categoria,
                    'tipo_juego': registro.tipo_juego,
                    'nivel_buyin': registro.nivel_buyin,
                    'sala': registro.sala
                })
            
            # Guardar backup en archivo
            backup_filename = f"backup_{current_user.username}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            backup_path = os.path.join(app.config['UPLOAD_FOLDER'], backup_filename)
            
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
            
            return {
                'mensaje': 'Backup creado exitosamente',
                'archivo': backup_filename,
                'total_registros': len(registros)
            }
            
        except Exception as e:
            return {'error': f'Error al crear backup: {str(e)}'}, 500

# Aquí continúo con las funciones de procesamiento de archivos que ya existen en app_multiusuario.py
# (Las copio de ahí para mantener la funcionalidad)

def generar_hash_duplicado(fecha, hora, payment_method, descripcion, money_in, money_out, sala):
    """Generar hash para detectar duplicados"""
    # Usar los campos más únicos para generar el hash
    unique_string = f"{fecha}_{hora}_{payment_method}_{descripcion}_{money_in}_{money_out}_{sala}"
    return hashlib.md5(unique_string.encode()).hexdigest()

def procesar_archivo_wpn(filepath, user_id):
    """Procesar archivo WPN Excel/XLS"""
    try:
        # Leer archivo Excel
        if filepath.endswith('.xlsx'):
            df = pd.read_excel(filepath, engine='openpyxl')
        else:
            df = pd.read_excel(filepath, engine='xlrd')
        
        print(f"Columnas encontradas: {list(df.columns)}")
        
        # Mapeo de columnas esperadas
        columnas_esperadas = {
            'Date': 'fecha',
            'Time': 'hora',
            'Payment Method': 'tipo_movimiento',
            'Description': 'descripcion',
            'Money In': 'money_in',
            'Money Out': 'money_out'
        }
        
        # Verificar que las columnas necesarias existen
        columnas_faltantes = [col for col in columnas_esperadas.keys() if col not in df.columns]
        if columnas_faltantes:
            raise Exception(f"Columnas faltantes en el archivo: {columnas_faltantes}")
        
        resultados_importados = 0
        duplicados_encontrados = 0
        duplicados_detalle = []
        sala = "WPN"  # Asumimos que es WPN
        
        for index, row in df.iterrows():
            try:
                # Procesar fecha
                fecha_str = str(row['Date'])
                if pd.isna(row['Date']) or fecha_str == 'nan':
                    continue
                
                # Convertir fecha
                if isinstance(row['Date'], str):
                    fecha = datetime.strptime(fecha_str, '%Y-%m-%d %H:%M:%S').date()
                else:
                    fecha = row['Date'].date() if hasattr(row['Date'], 'date') else row['Date']
                
                # Procesar hora
                hora_str = str(row['Time']) if not pd.isna(row['Time']) else "00:00:00"
                if hora_str == 'nan':
                    hora_str = "00:00:00"
                
                try:
                    if isinstance(row['Time'], str):
                        hora = datetime.strptime(hora_str, '%H:%M:%S').time()
                    else:
                        hora = row['Time'].time() if hasattr(row['Time'], 'time') else time(0, 0, 0)
                except:
                    hora = time(0, 0, 0)
                
                # Procesar otros campos
                payment_method = str(row['Payment Method']) if not pd.isna(row['Payment Method']) else ""
                descripcion = str(row['Description']) if not pd.isna(row['Description']) else ""
                money_in = float(row['Money In']) if not pd.isna(row['Money In']) and row['Money In'] != '' else 0.0
                money_out = float(row['Money Out']) if not pd.isna(row['Money Out']) and row['Money Out'] != '' else 0.0
                
                # Calcular importe (money_in es positivo, money_out es negativo)
                importe = money_in - money_out
                
                # Categorizar movimiento
                categoria, tipo_juego, nivel_buyin = categorizar_movimiento_wpn(descripcion, payment_method)
                
                # Generar hash para detectar duplicados
                hash_duplicado = generar_hash_duplicado(fecha, hora, payment_method, descripcion, money_in, money_out, sala)
                
                # Verificar si ya existe un registro con el mismo hash para el usuario
                existe_duplicado = PokerResult.query.filter_by(
                    user_id=user_id,
                    hash_duplicado=hash_duplicado
                ).first()
                
                if existe_duplicado:
                    duplicados_encontrados += 1
                    duplicados_detalle.append({
                        'fecha': fecha.isoformat(),
                        'descripcion': descripcion,
                        'importe': importe,
                        'razon': 'Hash duplicado'
                    })
                    continue
                
                # Crear nuevo registro
                resultado = PokerResult(
                    user_id=user_id,
                    fecha=fecha,
                    hora=hora,
                    tipo_movimiento=payment_method,
                    descripcion=descripcion,
                    importe=importe,
                    categoria=categoria,
                    tipo_juego=tipo_juego,
                    nivel_buyin=nivel_buyin,
                    sala=sala,
                    hash_duplicado=hash_duplicado
                )
                
                db.session.add(resultado)
                resultados_importados += 1
                
            except Exception as e:
                print(f"Error procesando fila {index}: {e}")
                continue
        
        # Confirmar cambios
        db.session.commit()
        
        return resultados_importados, duplicados_encontrados, duplicados_detalle
        
    except Exception as e:
        db.session.rollback()
        raise Exception(f"Error procesando archivo WPN: {str(e)}")

def categorizar_movimiento_wpn(descripcion, payment_method):
    """Categorizar movimientos WPN"""
    descripcion_lower = descripcion.lower()
    
    # Determinar categoría principal
    if any(term in descripcion_lower for term in ['tournament', 'tourney', 'mtt', 'sit & go', 'sng']):
        categoria = 'Torneo'
    elif any(term in descripcion_lower for term in ['cash', 'ring']):
        categoria = 'Cash'
    elif any(term in descripcion_lower for term in ['deposit', 'withdrawal', 'transfer']):
        categoria = 'Transferencia'
    else:
        categoria = 'Otros'
    
    # Determinar tipo de juego
    if 'hold' in descripcion_lower:
        tipo_juego = "Hold'em"
    elif 'omaha' in descripcion_lower:
        tipo_juego = 'Omaha'
    elif 'stud' in descripcion_lower:
        tipo_juego = 'Stud'
    else:
        tipo_juego = 'No especificado'
    
    # Determinar nivel de buy-in (simplificado)
    nivel_buyin = 'No especificado'
    
    return categoria, tipo_juego, nivel_buyin

def procesar_archivo_pokerstars(filepath, user_id):
    """Procesar archivo HTML de PokerStars"""
    try:
        # Leer el archivo HTML
        with open(filepath, 'r', encoding='utf-8') as file:
            content = file.read()
        
        soup = BeautifulSoup(content, 'html.parser')
        
        # Buscar la tabla de transacciones
        table = soup.find('table')
        if not table:
            raise Exception("No se encontró tabla de transacciones en el archivo HTML")
        
        rows = table.find_all('tr')[1:]  # Omitir el header
        
        resultados_importados = 0
        duplicados_encontrados = 0
        duplicados_detalle = []
        sala = "PokerStars"
        
        for row in rows:
            try:
                cells = row.find_all('td')
                if len(cells) < 6:
                    continue
                
                # Extraer datos
                fecha_hora_str = cells[0].get_text(strip=True)
                descripcion = cells[1].get_text(strip=True)
                importe_str = cells[2].get_text(strip=True)
                
                # Procesar fecha y hora
                fecha_hora = datetime.strptime(fecha_hora_str, '%Y/%m/%d %H:%M:%S')
                fecha = fecha_hora.date()
                hora = fecha_hora.time()
                
                # Procesar importe
                importe = float(importe_str.replace('$', '').replace(',', ''))
                
                # Categorizar
                categoria, tipo_juego, nivel_buyin, tipo_movimiento = categorizar_movimiento_pokerstars(descripcion)
                
                # Generar hash
                hash_duplicado = generar_hash_duplicado(fecha, hora, tipo_movimiento, descripcion, 0, 0, sala)
                
                # Verificar duplicados
                existe_duplicado = PokerResult.query.filter_by(
                    user_id=user_id,
                    hash_duplicado=hash_duplicado
                ).first()
                
                if existe_duplicado:
                    duplicados_encontrados += 1
                    duplicados_detalle.append({
                        'fecha': fecha.isoformat(),
                        'descripcion': descripcion,
                        'importe': importe,
                        'razon': 'Hash duplicado'
                    })
                    continue
                
                # Crear registro
                resultado = PokerResult(
                    user_id=user_id,
                    fecha=fecha,
                    hora=hora,
                    tipo_movimiento=tipo_movimiento,
                    descripcion=descripcion,
                    importe=importe,
                    categoria=categoria,
                    tipo_juego=tipo_juego,
                    nivel_buyin=nivel_buyin,
                    sala=sala,
                    hash_duplicado=hash_duplicado
                )
                
                db.session.add(resultado)
                resultados_importados += 1
                
            except Exception as e:
                print(f"Error procesando fila PokerStars: {e}")
                continue
        
        db.session.commit()
        return resultados_importados, duplicados_encontrados, duplicados_detalle
        
    except Exception as e:
        db.session.rollback()
        raise Exception(f"Error procesando archivo PokerStars: {str(e)}")

def categorizar_movimiento_pokerstars(descripcion):
    """Categorizar movimientos de PokerStars"""
    categoria = 'Otros'
    tipo_juego = 'No especificado'
    nivel_buyin = 'No especificado'
    tipo_movimiento = 'Otros'
    
    descripcion_lower = descripcion.lower()
    
    if 'tournament' in descripcion_lower:
        categoria = 'Torneo'
        tipo_movimiento = 'Buy In' if 'buy-in' in descripcion_lower else 'Prize'
    elif 'cash' in descripcion_lower:
        categoria = 'Cash'
    
    return categoria, tipo_juego, nivel_buyin, tipo_movimiento

# =============================================================================
# ENDPOINT DE ANÁLISIS AVANZADO
# =============================================================================

@analysis_ns.route('/insights')
class AnalisisInsights(Resource):
    @api.doc('get_analysis_insights')
    @api.response(200, 'Análisis obtenido exitosamente')
    @api.response(400, 'No hay datos para analizar', error_model)
    @api.response(500, 'Error interno', error_model)
    @require_auth
    def get(self):
        """Análisis avanzado con insights para gestión del juego"""
        try:
            # Obtener todos los registros de torneos del usuario actual
            torneos = PokerResult.query.filter(
                PokerResult.categoria == 'Torneo',
                PokerResult.user_id == current_user.id
            ).all()
            
            if not torneos:
                return {'error': 'No hay datos de torneos para analizar'}, 400
            
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
    @require_auth
    def get(self):
        """Análisis de rendimiento por nivel de buy-in"""
        try:
            torneos = PokerResult.query.filter(
                PokerResult.categoria == 'Torneo',
                PokerResult.user_id == current_user.id
            ).all()
            
            if not torneos:
                return {'error': 'No hay datos de torneos para analizar'}, 400
            
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
    @require_auth
    def get(self):
        """Análisis de rendimiento por sala"""
        try:
            torneos = PokerResult.query.filter(
                PokerResult.categoria == 'Torneo',
                PokerResult.user_id == current_user.id
            ).all()
            
            if not torneos:
                return {'error': 'No hay datos de torneos para analizar'}, 400
            
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
    @require_auth
    def get(self):
        """Análisis de patrones temporales"""
        try:
            torneos = PokerResult.query.filter(
                PokerResult.categoria == 'Torneo',
                PokerResult.user_id == current_user.id
            ).all()
            
            if not torneos:
                return {'error': 'No hay datos de torneos para analizar'}, 400
            
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
    @require_auth
    def get(self):
        """Análisis de rendimiento por tipo de juego"""
        try:
            torneos = PokerResult.query.filter(
                PokerResult.categoria == 'Torneo',
                PokerResult.user_id == current_user.id
            ).all()
            
            if not torneos:
                return {'error': 'No hay datos de torneos para analizar'}, 400
            
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
    @require_auth
    def get(self):
        """Análisis de consistencia del jugador"""
        try:
            torneos = PokerResult.query.filter(
                PokerResult.categoria == 'Torneo',
                PokerResult.user_id == current_user.id
            ).all()
            
            if not torneos:
                return {'error': 'No hay datos de torneos para analizar'}, 400
            
            analisis = analizar_consistencia_jugador(torneos)
            return analisis
            
        except Exception as e:
            return {'error': f'Error en análisis de consistencia: {str(e)}'}, 500

# =============================================================================
# FUNCIONES DE ANÁLISIS
# =============================================================================

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
                    'salas': set()
                }
            
            buyin_stats[torneo.nivel_buyin]['total_torneos'] += 1
            buyin_stats[torneo.nivel_buyin]['total_invertido'] += abs(torneo.importe) if torneo.importe < 0 else 0
            buyin_stats[torneo.nivel_buyin]['total_ganancias'] += torneo.importe if torneo.importe > 0 else 0
            buyin_stats[torneo.nivel_buyin]['salas'].add(torneo.sala)
    
    # Calcular ROI y rachas
    for nivel, stats in buyin_stats.items():
        if stats['total_invertido'] > 0:
            stats['roi'] = ((stats['total_ganancias'] - stats['total_invertido']) / stats['total_invertido']) * 100
        
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
    
    # Convertir a formato más amigable
    analisis_dias = {}
    for dia_num in range(7):
        nombre_dia = dias_nombres[dia_num]
        stats = dias_semana[dia_num]
        analisis_dias[nombre_dia] = {
            'torneos': stats['torneos'],
            'resultado': stats['resultado'],
            'resultado_promedio': stats['resultado'] / stats['torneos'] if stats['torneos'] > 0 else 0
        }
    
    analisis_horas = {}
    for hora in range(24):
        stats = horas_dia[hora]
        analisis_horas[f"{hora:02d}:00"] = {
            'torneos': stats['torneos'],
            'resultado': stats['resultado'],
            'resultado_promedio': stats['resultado'] / stats['torneos'] if stats['torneos'] > 0 else 0
        }
    
    return {
        'por_dia_semana': analisis_dias,
        'por_hora': analisis_horas
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
                    'torneos_ganados': 0,
                    'salas': set(),
                    'niveles_buyin': set()
                }
            
            stats = juego_stats[torneo.tipo_juego]
            stats['total_torneos'] += 1
            stats['total_invertido'] += abs(torneo.importe) if torneo.importe < 0 else 0
            stats['total_ganancias'] += torneo.importe if torneo.importe > 0 else 0
            
            if torneo.importe > 0:
                stats['torneos_ganados'] += 1
            
            if torneo.sala:
                stats['salas'].add(torneo.sala)
            
            if torneo.nivel_buyin:
                stats['niveles_buyin'].add(torneo.nivel_buyin)
    
    # Calcular métricas finales
    for tipo_juego, stats in juego_stats.items():
        if stats['total_invertido'] > 0:
            stats['roi'] = ((stats['total_ganancias'] - stats['total_invertido']) / stats['total_invertido']) * 100
        
        if stats['total_torneos'] > 0:
            stats['porcentaje_victorias'] = (stats['torneos_ganados'] / stats['total_torneos']) * 100
        
        # Convertir sets a listas para JSON
        stats['salas'] = list(stats['salas'])
        stats['niveles_buyin'] = list(stats['niveles_buyin'])
    
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
    dias_positivos = len([r for r in resultados if r > 0])
    dias_negativos = len([r for r in resultados if r < 0])
    dias_neutros = len([r for r in resultados if r == 0])
    
    # Rachas
    mejor_racha = max(resultados) if resultados else 0
    peor_racha = min(resultados) if resultados else 0
    
    return {
        'resultado_promedio_diario': media,
        'desviacion_estandar': desviacion,
        'coeficiente_variacion': coeficiente_variacion,
        'dias_analizados': len(resultados),
        'dias_positivos': dias_positivos,
        'dias_negativos': dias_negativos,
        'dias_neutros': dias_neutros,
        'mejor_dia': mejor_racha,
        'peor_dia': peor_racha,
        'consistencia_rating': 'Alta' if coeficiente_variacion < 50 else 'Media' if coeficiente_variacion < 100 else 'Baja'
    }

def generar_recomendaciones(analisis_buyin, analisis_temporal, analisis_juego, analisis_consistencia):
    """Genera recomendaciones estratégicas basadas en el análisis"""
    recomendaciones = []
    
    # Análisis de buy-in
    if analisis_buyin:
        mejor_buyin = max(analisis_buyin.items(), key=lambda x: x[1]['roi'])
        if mejor_buyin[1]['roi'] > 0:
            recomendaciones.append({
                'tipo': 'Buy-in',
                'mensaje': f"Tu mejor rendimiento es en buy-ins {mejor_buyin[0]} con {mejor_buyin[1]['roi']:.1f}% ROI",
                'accion': 'Considera aumentar el volumen en este nivel'
            })
    
    # Análisis temporal
    if analisis_temporal and 'por_dia_semana' in analisis_temporal:
        mejor_dia = max(analisis_temporal['por_dia_semana'].items(), key=lambda x: x[1]['resultado_promedio'])
        if mejor_dia[1]['resultado_promedio'] > 0:
            recomendaciones.append({
                'tipo': 'Temporal',
                'mensaje': f"Los {mejor_dia[0]} son tu mejor día con promedio de ${mejor_dia[1]['resultado_promedio']:.2f}",
                'accion': 'Planifica más sesiones en este día'
            })
    
    # Análisis de consistencia
    if analisis_consistencia:
        if analisis_consistencia.get('dias_positivos', 0) > analisis_consistencia.get('dias_negativos', 0):
            recomendaciones.append({
                'tipo': 'Consistencia',
                'mensaje': f"Tienes más días positivos ({analisis_consistencia['dias_positivos']}) que negativos ({analisis_consistencia['dias_negativos']})",
                'accion': 'Mantén tu estrategia actual'
            })
        else:
            recomendaciones.append({
                'tipo': 'Consistencia',
                'mensaje': "Tienes más días negativos que positivos",
                'accion': 'Revisa tu gestión de bankroll y selección de juegos'
            })
    
    return recomendaciones

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5001)
