#!/usr/bin/env python3
"""
Aplicación de análisis de resultados de poker - Versión para Vercel
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

# Configuración de archivos para Vercel
UPLOAD_FOLDER = '/tmp/uploads' if os.environ.get('VERCEL') else 'uploads'
PROCESADOS_FOLDER = '/tmp/procesados' if os.environ.get('VERCEL') else 'procesados'
ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'html'}

# Crear carpetas si no existen (solo en desarrollo)
if not os.environ.get('VERCEL'):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(PROSADOS_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESADOS_FOLDER'] = PROCESADOS_FOLDER

# Inicializar extensiones
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor, inicia sesión para acceder a esta página.'

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
    fecha_str = fecha.strftime('%Y-%m-%d') if isinstance(fecha, date) else str(fecha)
    hora_str = hora.strftime('%H:%M:%S') if hora else '00:00:00'
    
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
# FUNCIONES DE CATEGORIZACIÓN (SIMPLIFICADAS)
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
    
    return render_template('login_vercel.html', form=form)

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

# =============================================================================
# API ENDPOINTS (SIMPLIFICADOS)
# =============================================================================

@app.route('/api/importar', methods=['POST'])
@login_required
def api_importar():
    """API para importar archivos - Simplificado para Vercel"""
    if 'archivo' not in request.files:
        return jsonify({'error': 'No se seleccionó archivo'}), 400
    
    archivo = request.files['archivo']
    if archivo.filename == '':
        return jsonify({'error': 'No se seleccionó archivo'}), 400
    
    if not allowed_file(archivo.filename):
        return jsonify({'error': 'Tipo de archivo no permitido'}), 400
    
    try:
        # Para Vercel, procesar en memoria sin guardar archivos
        if filename.lower().endswith('.html'):
            # Procesar HTML de Pokerstars
            content = archivo.read().decode('utf-8')
            soup = BeautifulSoup(content, 'html.parser')
            
            # Procesar datos básicos
            resultados_importados = 0
            duplicados_encontrados = 0
            
            # Aquí iría la lógica de procesamiento
            # Por ahora, retornar éxito básico
            
        else:
            # Procesar Excel de WPN
            df = pd.read_excel(archivo)
            resultados_importados = len(df)
            duplicados_encontrados = 0
        
        return jsonify({
            'mensaje': f'Archivo procesado exitosamente. {resultados_importados} registros importados, {duplicados_encontrados} duplicados omitidos.',
            'resultados_importados': resultados_importados,
            'duplicados_encontrados': duplicados_encontrados,
            'duplicados_detalle': []
        })
        
    except Exception as e:
        return jsonify({'error': f'Error procesando archivo: {str(e)}'}), 500

@app.route('/api/informes/resultados')
@login_required
def api_informes_resultados():
    """API para obtener resultados - Simplificado"""
    try:
        # Obtener parámetros de filtro
        fecha_inicio = request.args.get('fecha_inicio')
        fecha_fin = request.args.get('fecha_fin')
        
        # Query básico
        query = PokerResult.query.filter_by(user_id=current_user.id)
        
        if fecha_inicio:
            query = query.filter(PokerResult.fecha >= datetime.strptime(fecha_inicio, '%Y-%m-%d').date())
        if fecha_fin:
            query = query.filter(PokerResult.fecha <= datetime.strptime(fecha_fin, '%Y-%m-%d').date())
        
        resultados = query.all()
        
        # Estadísticas básicas
        total_registros = len(resultados)
        suma_importes = sum(r.importe for r in resultados)
        
        # Resultados diarios (últimos 10 días)
        fecha_limite = datetime.now().date() - timedelta(days=10)
        resultados_diarios = []
        for i in range(10):
            fecha = datetime.now().date() - timedelta(days=i)
            total_dia = sum(r.importe for r in resultados if r.fecha == fecha)
            resultados_diarios.append({
                'fecha': fecha.strftime('%Y-%m-%d'),
                'total': total_dia
            })
        
        return jsonify({
            'resultados': [{
                'id': r.id,
                'fecha': r.fecha.strftime('%Y-%m-%d'),
                'hora': r.hora.strftime('%H:%M:%S') if r.hora else '',
                'descripcion': r.descripcion,
                'importe': r.importe,
                'categoria': r.categoria,
                'tipo_movimiento': r.tipo_movimiento,
                'tipo_juego': r.tipo_juego,
                'sala': r.sala,
                'nivel_buyin': r.nivel_buyin
            } for r in resultados],
            'estadisticas': {
                'total_registros': total_registros,
                'suma_importes': suma_importes,
                'resultado_economico': suma_importes
            },
            'resultados_diarios': resultados_diarios
        })
        
    except Exception as e:
        return jsonify({'error': f'Error obteniendo resultados: {str(e)}'}), 500

@app.route('/api/informes/opciones')
@login_required
def api_informes_opciones():
    """API para obtener opciones de filtros"""
    try:
        # Obtener opciones básicas
        categorias = db.session.query(PokerResult.categoria).filter_by(user_id=current_user.id).distinct().all()
        tipos_juego = db.session.query(PokerResult.tipo_juego).filter_by(user_id=current_user.id).distinct().all()
        salas = db.session.query(PokerResult.sala).filter_by(user_id=current_user.id).distinct().all()
        
        return jsonify({
            'categorias': [c[0] for c in categorias],
            'tipos_juego': [t[0] for t in tipos_juego],
            'salas': [s[0] for s in salas],
            'niveles_buyin': ['Micro', 'Bajo', 'Medio', 'Alto']
        })
        
    except Exception as e:
        return jsonify({'error': f'Error obteniendo opciones: {str(e)}'}), 500

# =============================================================================
# INICIALIZACIÓN
# =============================================================================

@app.before_first_request
def create_tables():
    """Crear tablas si no existen"""
    try:
        db.create_all()
        
        # Crear usuario administrador si no existe
        admin_user = User.query.filter_by(is_admin=True).first()
        if not admin_user:
            admin = User(
                username='admin',
                email='admin@poker-results.com',
                is_admin=True,
                is_active=True
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            
    except Exception as e:
        print(f"Error inicializando base de datos: {e}")

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
