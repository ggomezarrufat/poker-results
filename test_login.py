#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

def test_supabase_connection():
    """Probar conexión con Supabase"""
    print("🔍 Probando conexión con Supabase...")
    
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY')
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ Error: SUPABASE_URL y SUPABASE_KEY deben estar configurados")
        return False
    
    try:
        # Crear cliente de Supabase
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Probar conexión obteniendo usuarios
        print("📡 Probando consulta a la tabla users...")
        response = supabase.table('users').select('*').limit(1).execute()
        
        if response.data is not None:
            print(f"✅ Conexión exitosa. Usuarios encontrados: {len(response.data)}")
            if response.data:
                print(f"📋 Primer usuario: {response.data[0]['username']}")
            return True
        else:
            print("❌ No se pudieron obtener datos de la tabla users")
            return False
            
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return False

def test_user_creation():
    """Probar creación de usuario"""
    print("\n🔍 Probando creación de usuario...")
    
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY')
    
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Datos de prueba
        test_user = {
            'username': 'test_user',
            'email': 'test@example.com',
            'password_hash': 'test_hash',
            'is_admin': False,
            'is_active': True
        }
        
        print("📝 Intentando crear usuario de prueba...")
        response = supabase.table('users').insert(test_user).execute()
        
        if response.data:
            print("✅ Usuario creado exitosamente")
            print(f"📋 Usuario creado: {response.data[0]['username']}")
            return True
        else:
            print("❌ No se pudo crear el usuario")
            return False
            
    except Exception as e:
        print(f"❌ Error creando usuario: {e}")
        return False

def test_user_login():
    """Probar login de usuario"""
    print("\n🔍 Probando login de usuario...")
    
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY')
    
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Buscar usuario
        print("🔍 Buscando usuario 'test_user'...")
        response = supabase.table('users').select('*').eq('username', 'test_user').execute()
        
        if response.data:
            print(f"✅ Usuario encontrado: {response.data[0]['username']}")
            print(f"📋 Email: {response.data[0]['email']}")
            print(f"📋 Activo: {response.data[0]['is_active']}")
            return True
        else:
            print("❌ Usuario no encontrado")
            return False
            
    except Exception as e:
        print(f"❌ Error en login: {e}")
        return False

if __name__ == '__main__':
    print("🚀 Prueba de conexión y login con Supabase")
    print("=" * 50)
    
    # Probar conexión
    connection_ok = test_supabase_connection()
    
    if connection_ok:
        # Probar creación de usuario
        creation_ok = test_user_creation()
        
        if creation_ok:
            # Probar login
            login_ok = test_user_login()
            
            if login_ok:
                print("\n🎉 ¡Todas las pruebas pasaron exitosamente!")
            else:
                print("\n❌ Error en el login")
        else:
            print("\n❌ Error en la creación de usuario")
    else:
        print("\n❌ Error en la conexión con Supabase")
