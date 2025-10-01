#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from flask import Flask, request, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from supabase import create_client, Client

# Carg🚀 Iniciando aplicación Poker Results...
📍 URL de Supabase: https://ovtromeyunbhgndqlncb.supabase.co
✅ Aplicación lista en http://localhost:5001
🚀 Iniciando aplicación Poker Results...
📍 URL de Supabase: https://ovtromeyunbhgndqlncb.supabase.co
✅ Aplicación lista en http://localhost:5001
rror('SUPABASE_URL y SUPABASE_KEY deben estar configurados en el archivo .env')

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
        self.is_active = is_active

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

@app.route('/')
@login_required
def index():
    return 'Aplicación Poker Results funcionando correctamente con Supabase!'

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
                    return 'Login exitoso!'
                else:
                    return 'Credenciales incorrectas', 401
            else:
                return 'Usuario no encontrado', 401
        except Exception as e:
            return f'Error en login: {e}', 500
    
    return 'Página de login'

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return 'Logout exitoso!'

if __name__ == '__main__':
    print('🚀 Iniciando aplicación Poker Results...')
    print(f'📍 URL de Supabase: {SUPABASE_URL}')
    print('✅ Aplicación lista en http://localhost:5001')
    app.run(debug=True, host='0.0.0.0', port=5001)