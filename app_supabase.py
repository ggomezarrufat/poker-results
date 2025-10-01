#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import uuid
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, validators
from supabase import create_client, Client
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')

# Configurar Supabase
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL y SUPABASE_KEY deben estar configurados en el archivo .env")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Configurar Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor, inicia sesión para acceder a esta página.'

# Clase User para Flask-Login
class User(UserMixin):
    def __init__(self, id, username, email, is_admin=False, is_active=True):
        self.id = id
        self.username = username
        self.email = email
        self.is_admin = is_admin
        self.is_active = is_active

@login_manager.user_loader
def load_user(user_id):
    try:
        # Buscar usuario en Supabase
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
            # Buscar usuario en Supabase
            response = supabase.table('users').select('*').eq('username', form.username.data).execute()
            
            if response.data:
                user_data = response.data[0]
                # Verificar contraseña
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
            password_hash = generate_password_hash(form.password.data)
            
            user_data = {
                'id': user_id,
                'username': form.username.data,
                'email': form.email.data,
                'password_hash': password_hash,
                'is_admin': False,
                'is_active': True,
                'created_at': datetime.now().isoformat()
            }
            
            supabase.table('users').insert(user_data).execute()
            
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
@login_required
def analisis():
    """Página de análisis"""
    try:
        # Obtener datos del usuario actual
        user_data = supabase.table('poker_results').select('*').eq('user_id', current_user.id).execute()
        records = user_data.data if user_data.data else []
        
        return render_template('analisis.html', records=records)
    except Exception as e:
        flash('Error al cargar datos de análisis.', 'error')
        print(f"Error en análisis: {e}")
        return render_template('analisis.html', records=[])

@app.route('/informes')
@login_required
def informes():
    """Página de informes"""
    try:
        # Obtener datos del usuario actual
        user_data = supabase.table('poker_results').select('*').eq('user_id', current_user.id).execute()
        records = user_data.data if user_data.data else []
        
        return render_template('informes.html', records=records)
    except Exception as e:
        flash('Error al cargar datos de informes.', 'error')
        print(f"Error en informes: {e}")
        return render_template('informes.html', records=[])

if __name__ == '__main__':
    print("🚀 Iniciando aplicación con Supabase...")
    print(f"📡 Supabase URL: {SUPABASE_URL}")
    print(f"🔑 Supabase Key: {SUPABASE_KEY[:20]}...")
    
    app.run(debug=True, host='0.0.0.0', port=5001)
