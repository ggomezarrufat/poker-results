#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import uuid
from datetime import datetime
from werkzeug.security import generate_password_hash
from supabase import create_client, Client
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configurar Supabase
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL y SUPABASE_KEY deben estar configurados en el archivo .env")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def create_admin_user():
    """Crear usuario admin con hash de contraseña correcto"""
    try:
        # Verificar si ya existe el usuario admin
        existing_admin = supabase.table('users').select('*').eq('username', 'admin').execute()
        
        if existing_admin.data:
            print("❌ El usuario admin ya existe")
            return False
        
        # Crear usuario admin
        admin_id = '00000000-0000-0000-0000-000000000001'  # UUID fijo para admin
        password_hash = generate_password_hash('admin123', method='scrypt')
        
        admin_data = {
            'id': admin_id,
            'username': 'admin',
            'email': 'admin@poker.com',
            'password_hash': password_hash,
            'is_admin': True,
            'is_active': True,
            'created_at': datetime.now().isoformat()
        }
        
        result = supabase.table('users').insert(admin_data).execute()
        
        if result.data:
            print("✅ Usuario admin creado exitosamente")
            print(f"   Usuario: admin")
            print(f"   Contraseña: admin123")
            print(f"   ID: {admin_id}")
            return True
        else:
            print("❌ Error al crear usuario admin")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == '__main__':
    print("🚀 Creando usuario admin...")
    create_admin_user()