#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script para probar el registro de usuarios y identificar errores
"""

import os
import uuid
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

# Cargar variables de entorno
load_dotenv()

# Configurar Supabase
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL y SUPABASE_KEY deben estar configurados en el archivo .env")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def test_user_registration():
    """Probar el registro de un usuario de prueba"""
    try:
        print("🧪 Probando registro de usuario...")
        
        # Datos de usuario de prueba
        test_username = f"test_user_{uuid.uuid4().hex[:8]}"
        test_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
        test_password = "test_password_123"
        
        print(f"📝 Usuario de prueba: {test_username}")
        print(f"📧 Email de prueba: {test_email}")
        
        # Verificar si el usuario ya existe
        print("🔍 Verificando si el usuario ya existe...")
        existing_user = supabase.table('users').select('username').eq('username', test_username).execute()
        if existing_user.data:
            print("⚠️  El usuario ya existe")
            return False
        
        existing_email = supabase.table('users').select('email').eq('email', test_email).execute()
        if existing_email.data:
            print("⚠️  El email ya existe")
            return False
        
        print("✅ Usuario y email disponibles")
        
        # Crear nuevo usuario
        print("🔐 Generando hash de contraseña...")
        user_id = str(uuid.uuid4())
        password_hash = generate_password_hash(test_password, method='scrypt')
        
        print(f"🆔 ID de usuario: {user_id}")
        print(f"🔑 Hash de contraseña: {password_hash[:50]}...")
        
        user_data = {
            'id': user_id,
            'username': test_username,
            'email': test_email,
            'password_hash': password_hash,
            'is_admin': False,
            'is_active': True,
            'created_at': datetime.now().isoformat()
        }
        
        print("💾 Insertando usuario en la base de datos...")
        result = supabase.table('users').insert(user_data).execute()
        
        print("✅ Usuario registrado exitosamente!")
        print(f"📊 Resultado: {result}")
        
        # Verificar que el usuario se creó correctamente
        print("🔍 Verificando que el usuario se creó...")
        created_user = supabase.table('users').select('*').eq('id', user_id).execute()
        if created_user.data:
            print("✅ Usuario encontrado en la base de datos")
            print(f"📋 Datos: {created_user.data[0]}")
        else:
            print("❌ Usuario no encontrado en la base de datos")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error en el registro: {e}")
        print(f"🔍 Tipo de error: {type(e).__name__}")
        return False

def test_database_connection():
    """Probar la conexión a la base de datos"""
    try:
        print("🔍 Probando conexión a Supabase...")
        
        # Probar conexión con una consulta simple
        result = supabase.table('users').select('id').limit(1).execute()
        print("✅ Conexión a Supabase exitosa")
        print(f"📊 Datos de prueba: {result}")
        return True
        
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return False

def cleanup_test_user():
    """Limpiar usuario de prueba"""
    try:
        print("🧹 Limpiando usuario de prueba...")
        
        # Buscar y eliminar usuarios de prueba
        test_users = supabase.table('users').select('id').like('username', 'test_user_%').execute()
        
        if test_users.data:
            for user in test_users.data:
                supabase.table('users').delete().eq('id', user['id']).execute()
                print(f"🗑️  Usuario {user['id']} eliminado")
        
        print("✅ Limpieza completada")
        
    except Exception as e:
        print(f"⚠️  Error en limpieza: {e}")

if __name__ == '__main__':
    print("🚀 Iniciando pruebas de registro...")
    
    # Probar conexión primero
    if not test_database_connection():
        print("❌ No se puede conectar a Supabase. Verifica las credenciales.")
        exit(1)
    
    # Probar registro
    if test_user_registration():
        print("🎉 ¡Registro de usuario exitoso!")
    else:
        print("❌ Error en el registro de usuario")
    
    # Limpiar
    cleanup_test_user()
    
    print("🏁 Pruebas completadas")
