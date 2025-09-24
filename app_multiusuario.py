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
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SelectField, SubmitField, DateField, IntegerField
from wtforms.validators import DataRequired, Length, Email, EqualTo
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///poker_results.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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
login_manager.login_message = 'Por favor, inicia sesión para acceder a esta página.'

# Configurar Supabase
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

# =============================================================================
# MODELOS DE BASE DE DATOS
# =============================================================================

class User(UserMixin, db.Model):
    """Modelo de usuario"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Relación con resultados de poker
    poker_results = db.relationship('PokerResult', backref='user', lazy=True)
    
    def set_password(self, password):
        """Establecer contraseña hasheada"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verificar contraseña"""
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'

class PokerResult(db.Model):
    """Modelo de resultados de poker - Modificado para multiusuario"""
    __tablename__ = 'poker_results'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    hora = db.Column(db.Time, nullable=True)
    descripcion = db.Column(db.String(500), nullable=False)
    importe = db.Column(db.Float, nullable=False)
    categoria = db.Column(db.String(50), nullable=False)
    tipo_movimiento = db.Column(db.String(50), nullable=False)
    tipo_juego = db.Column(db.String(50), nullable=False)
    sala = db.Column(db.String(50), nullable=False)
    nivel_buyin = db.Column(db.String(20), nullable=True)
    hash_duplicado = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Índices para mejorar rendimiento
    __table_args__ = (
        db.Index('idx_user_fecha', 'user_id', 'fecha'),
        db.Index('idx_user_categoria', 'user_id', 'categoria'),
        db.Index('idx_user_sala', 'user_id', 'sala'),
        db.Index('idx_hash_duplicado', 'hash_duplicado'),
    )

# =============================================================================
# FORMULARIOS
# =============================================================================

class LoginForm(FlaskForm):
    """Formulario de login"""
    username = StringField('Usuario', validators=[DataRequired(), Length(min=3, max=20)])
    password = PasswordField('Contraseña', validators=[DataRequired()])
    remember_me = BooleanField('Recordarme')
    submit = SubmitField('Iniciar Sesión')

class UserForm(FlaskForm):
    """Formulario para crear/editar usuarios"""
    username = StringField('Usuario', validators=[DataRequired(), Length(min=3, max=20)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Contraseña', validators=[DataRequired(), Length(min=6)])
    password2 = PasswordField('Confirmar Contraseña', validators=[DataRequired(), EqualTo('password')])
    is_admin = BooleanField('Es Administrador')
    is_active = BooleanField('Usuario Activo', default=True)
    submit = SubmitField('Guardar Usuario')

class ChangePasswordForm(FlaskForm):
    """Formulario para cambiar contraseña"""
    current_password = PasswordField('Contraseña Actual', validators=[DataRequired()])
    new_password = PasswordField('Nueva Contraseña', validators=[DataRequired(), Length(min=6)])
    new_password2 = PasswordField('Confirmar Nueva Contraseña', validators=[DataRequired(), EqualTo('new_password')])
    submit = SubmitField('Cambiar Contraseña')

class AdminUserSelectForm(FlaskForm):
    """Formulario para seleccionar usuario en análisis de admin"""
    user_id = SelectField('Seleccionar Usuario', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Ver Análisis')

# =============================================================================
# FUNCIONES DE UTILIDAD
# =============================================================================

@login_manager.user_loader
def load_user(user_id):
    """Cargar usuario para Flask-Login"""
    return User.query.get(int(user_id))

def allowed_file(filename):
    """Verificar si el archivo tiene extensión permitida"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generar_hash_duplicado(fecha, hora, descripcion, importe, payment_method=None, money_in=None, money_out=None):
    """Generar hash único para detectar duplicados"""
    # Crear string único combinando todos los campos relevantes
    fecha_str = fecha.strftime('%Y-%m-%d') if isinstance(fecha, date) else str(fecha)
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
        if 'stud' in desc_lower and ('hi/lo' in desc_lower or 'hi lo' in desc_lower):
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

# =============================================================================
# FUNCIONES DE RECLASIFICACIÓN (MANTENIDAS DEL CÓDIGO ORIGINAL)
# =============================================================================

def reclasificar_niveles_buyin_automatica():
    """Reclasifica automáticamente los niveles de buy-in para registros de torneos"""
    try:
        # Obtener todos los registros de torneos con Buy In que ya tienen nivel_buyin
        buyins_clasificados = PokerResult.query.filter(
            PokerResult.categoria == 'Torneo',
            PokerResult.tipo_movimiento == 'Buy In',
            PokerResult.nivel_buyin.isnot(None),
            PokerResult.user_id == current_user.id
        ).all()
        
        if not buyins_clasificados:
            return 0
        
        # Obtener registros de torneos sin clasificar
        registros_sin_clasificar = PokerResult.query.filter(
            PokerResult.categoria == 'Torneo',
            PokerResult.tipo_movimiento.in_(['Bounty', 'Winnings', 'Sit & Crush Jackpot', 'Fee', 'Reentry Fee', 'Reentry Buy In', 'Unregister Buy In', 'Unregister Fee', 'Tournament Rebuy', 'Ticket']),
            PokerResult.nivel_buyin.is_(None),
            PokerResult.user_id == current_user.id
        ).all()
        
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
                
                # Método 3: Clasificar por importe si no se encuentra coincidencia
                if not nivel_buyin:
                    nivel_buyin = clasificar_nivel_buyin(abs(registro.importe))
                
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
    try:
        # Obtener todos los registros Buy In con tipo de juego específico
        buyins_clasificados = PokerResult.query.filter(
            PokerResult.categoria == 'Torneo',
            PokerResult.tipo_movimiento == 'Buy In',
            PokerResult.tipo_juego != 'Torneo',
            PokerResult.user_id == current_user.id
        ).all()
        
        if not buyins_clasificados:
            return 0
        
        # Crear diccionario de descripción -> tipo_juego
        descripcion_tipo_juego = {}
        for buyin in buyins_clasificados:
            descripcion_tipo_juego[buyin.descripcion] = buyin.tipo_juego
        
        # Obtener registros que necesitan reclasificación
        registros_sin_clasificar = PokerResult.query.filter(
            PokerResult.categoria == 'Torneo',
            PokerResult.tipo_movimiento.in_(['Reentry Buy In', 'Winnings', 'Bounty', 'Fee', 'Reentry Fee', 'Unregister Buy In', 'Unregister Fee', 'Sit & Crush Jackpot', 'Tournament Rebuy', 'Ticket']),
            PokerResult.tipo_juego == 'Torneo',
            PokerResult.user_id == current_user.id
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
                print(f"Error reclasificando tipo de juego para registro {registro.id}: {e}")
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
        user = User.query.filter_by(username=form.username.data).first()
        
        if user and user.check_password(form.password.data) and user.is_active:
            login_user(user, remember=form.remember_me.data)
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/'):
                next_page = url_for('index')
            return redirect(next_page)
        else:
            flash('Usuario o contraseña incorrectos, o cuenta desactivada.', 'error')
    
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    """Cerrar sesión"""
    logout_user()
    return redirect(url_for('login'))

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
    
    users = User.query.all()
    return render_template('admin.html', users=users)

@app.route('/admin/users')
@login_required
def admin_users():
    """Gestión de usuarios"""
    if not current_user.is_admin:
        flash('No tienes permisos para acceder a esta página.', 'error')
        return redirect(url_for('index'))
    
    users = User.query.all()
    return render_template('admin_users.html', users=users)

@app.route('/admin/users/new', methods=['GET', 'POST'])
@login_required
def admin_new_user():
    """Crear nuevo usuario"""
    if not current_user.is_admin:
        flash('No tienes permisos para acceder a esta página.', 'error')
        return redirect(url_for('index'))
    
    form = UserForm()
    if form.validate_on_submit():
        # Verificar si el usuario ya existe
        if User.query.filter_by(username=form.username.data).first():
            flash('El nombre de usuario ya existe.', 'error')
            return render_template('admin_user_form.html', form=form, title='Crear Usuario')
        
        if User.query.filter_by(email=form.email.data).first():
            flash('El email ya está registrado.', 'error')
            return render_template('admin_user_form.html', form=form, title='Crear Usuario')
        
        user = User(
            username=form.username.data,
            email=form.email.data,
            is_admin=form.is_admin.data,
            is_active=form.is_active.data
        )
        user.set_password(form.password.data)
        
        db.session.add(user)
        db.session.commit()
        
        flash('Usuario creado exitosamente.', 'success')
        return redirect(url_for('admin_users'))
    
    return render_template('admin_user_form.html', form=form, title='Crear Usuario')

@app.route('/admin/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_edit_user(user_id):
    """Editar usuario"""
    if not current_user.is_admin:
        flash('No tienes permisos para acceder a esta página.', 'error')
        return redirect(url_for('index'))
    
    user = User.query.get_or_404(user_id)
    form = UserForm(obj=user)
    
    if form.validate_on_submit():
        # Verificar si el username ya existe en otro usuario
        existing_user = User.query.filter(User.username == form.username.data, User.id != user_id).first()
        if existing_user:
            flash('El nombre de usuario ya existe.', 'error')
            return render_template('admin_user_form.html', form=form, title='Editar Usuario', user=user)
        
        # Verificar si el email ya existe en otro usuario
        existing_email = User.query.filter(User.email == form.email.data, User.id != user_id).first()
        if existing_email:
            flash('El email ya está registrado.', 'error')
            return render_template('admin_user_form.html', form=form, title='Editar Usuario', user=user)
        
        user.username = form.username.data
        user.email = form.email.data
        user.is_admin = form.is_admin.data
        user.is_active = form.is_active.data
        
        if form.password.data:  # Solo cambiar contraseña si se proporciona
            user.set_password(form.password.data)
        
        db.session.commit()
        flash('Usuario actualizado exitosamente.', 'success')
        return redirect(url_for('admin_users'))
    
    return render_template('admin_user_form.html', form=form, title='Editar Usuario', user=user)

@app.route('/admin/analisis')
@login_required
def admin_analisis():
    """Análisis de administrador con selección de usuario"""
    if not current_user.is_admin:
        flash('No tienes permisos para acceder a esta página.', 'error')
        return redirect(url_for('index'))
    
    form = AdminUserSelectForm()
    form.user_id.choices = [(u.id, f"{u.username} ({u.email})") for u in User.query.filter_by(is_active=True).all()]
    
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
        
        return jsonify({
            'mensaje': f'Archivo procesado exitosamente. {resultados_importados} registros importados, {duplicados_encontrados} duplicados omitidos.',
            'resultados_importados': resultados_importados,
            'duplicados_encontrados': duplicados_encontrados,
            'duplicados_detalle': duplicados_detalle
        })
        
    except Exception as e:
        return jsonify({'error': f'Error procesando archivo: {str(e)}'}), 500

# Continuará en la siguiente parte...

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)

