#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script para verificar y corregir RLS en Supabase
"""

import os
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

def check_rls_status():
    """Verificar el estado de RLS en las tablas"""
    try:
        print("🔍 Verificando estado de RLS...")
        
        # Intentar una consulta simple para ver si RLS está activo
        try:
            result = supabase.table('users').select('*').limit(1).execute()
            print("✅ Consulta SELECT exitosa")
            print(f"📊 Datos: {result.data}")
        except Exception as e:
            print(f"❌ Error en consulta SELECT: {e}")
        
        # Intentar insertar un registro de prueba para ver si RLS bloquea
        try:
            test_data = {
                'id': 'test-rls-check',
                'username': 'test_rls_user',
                'email': 'test@example.com',
                'password_hash': 'test_hash',
                'is_admin': False,
                'is_active': True
            }
            
            result = supabase.table('users').insert(test_data).execute()
            print("✅ Inserción exitosa - RLS puede estar deshabilitado")
            
            # Limpiar el registro de prueba
            supabase.table('users').delete().eq('id', 'test-rls-check').execute()
            print("🧹 Registro de prueba eliminado")
            
        except Exception as e:
            print(f"❌ Error en inserción: {e}")
            if "row-level security policy" in str(e):
                print("🔒 RLS está activo y bloqueando inserciones")
            else:
                print(f"🔍 Otro tipo de error: {e}")
        
    except Exception as e:
        print(f"❌ Error general: {e}")

def test_simple_insert():
    """Probar una inserción simple"""
    try:
        print("🧪 Probando inserción simple...")
        
        # Datos mínimos para la inserción
        test_data = {
            'username': 'simple_test_user',
            'email': 'simple@test.com',
            'password_hash': 'test_hash_123',
            'is_admin': False,
            'is_active': True
        }
        
        print(f"📝 Datos a insertar: {test_data}")
        
        result = supabase.table('users').insert(test_data).execute()
        print("✅ Inserción exitosa!")
        print(f"📊 Resultado: {result}")
        
        # Limpiar
        if result.data:
            user_id = result.data[0]['id']
            supabase.table('users').delete().eq('id', user_id).execute()
            print("🧹 Registro de prueba eliminado")
        
    except Exception as e:
        print(f"❌ Error en inserción simple: {e}")

if __name__ == '__main__':
    print("🚀 Verificando estado de RLS en Supabase...")
    
    check_rls_status()
    print("\n" + "="*50 + "\n")
    test_simple_insert()
    
    print("\n🏁 Verificación completada")
