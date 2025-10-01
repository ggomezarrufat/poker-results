#!/usr/bin/env python3
"""
Script de prueba para verificar la conexión con Supabase
"""

import os
import sys
from dotenv import load_dotenv
import psycopg2
from psycopg2 import sql

def test_supabase_connection():
    """Prueba la conexión con Supabase"""
    print("🔍 Probando conexión con Supabase...")
    print("=" * 50)
    
    # Cargar variables de entorno
    load_dotenv()
    
    # Obtener variables de entorno
    database_url = os.environ.get('DATABASE_URL')
    supabase_url = os.environ.get('SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_KEY')
    
    print(f"📋 Variables de entorno:")
    print(f"   DATABASE_URL: {'✅ Configurado' if database_url else '❌ No configurado'}")
    print(f"   SUPABASE_URL: {'✅ Configurado' if supabase_url else '❌ No configurado'}")
    print(f"   SUPABASE_KEY: {'✅ Configurado' if supabase_key else '❌ No configurado'}")
    print()
    
    if not database_url:
        print("❌ ERROR: DATABASE_URL no está configurado en el archivo .env")
        return False
    
    # Probar conexión a la base de datos
    print("🔌 Probando conexión a la base de datos...")
    try:
        conn = psycopg2.connect(database_url)
        print("✅ Conexión a la base de datos exitosa!")
        
        # Crear cursor
        cursor = conn.cursor()
        
        # Probar consulta simple
        print("📊 Probando consulta simple...")
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"✅ Versión de PostgreSQL: {version[0]}")
        
        # Verificar si las tablas existen
        print("🗃️  Verificando tablas...")
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        tables = cursor.fetchall()
        
        if tables:
            print("✅ Tablas encontradas:")
            for table in tables:
                print(f"   - {table[0]}")
        else:
            print("⚠️  No se encontraron tablas en el esquema 'public'")
            print("   💡 Necesitas ejecutar el script SQL en Supabase")
        
        # Cerrar conexión
        cursor.close()
        conn.close()
        print("✅ Conexión cerrada correctamente")
        
        return True
        
    except psycopg2.OperationalError as e:
        print(f"❌ ERROR de conexión: {e}")
        print("\n🔧 Posibles soluciones:")
        print("   1. Verificar que el proyecto de Supabase esté activo")
        print("   2. Verificar las credenciales en el archivo .env")
        print("   3. Verificar la conexión a internet")
        print("   4. Verificar que el proyecto no esté pausado")
        return False
        
    except Exception as e:
        print(f"❌ ERROR inesperado: {e}")
        return False

def test_supabase_api():
    """Prueba la conexión a la API de Supabase"""
    print("\n🌐 Probando conexión a la API de Supabase...")
    print("=" * 50)
    
    try:
        import requests
        
        supabase_url = os.environ.get('SUPABASE_URL')
        supabase_key = os.environ.get('SUPABASE_KEY')
        
        if not supabase_url or not supabase_key:
            print("❌ SUPABASE_URL o SUPABASE_KEY no configurados")
            return False
        
        # Probar endpoint de salud
        health_url = f"{supabase_url}/rest/v1/"
        headers = {
            'apikey': supabase_key,
            'Authorization': f'Bearer {supabase_key}'
        }
        
        response = requests.get(health_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            print("✅ API de Supabase accesible")
            return True
        else:
            print(f"⚠️  API respondió con código: {response.status_code}")
            return False
            
    except ImportError:
        print("⚠️  requests no está instalado, saltando prueba de API")
        return None
    except Exception as e:
        print(f"❌ ERROR en API: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Prueba de conexión con Supabase")
    print("=" * 50)
    
    # Probar conexión a base de datos
    db_success = test_supabase_connection()
    
    # Probar API
    api_success = test_supabase_api()
    
    print("\n📋 Resumen:")
    print("=" * 50)
    print(f"Base de datos: {'✅ OK' if db_success else '❌ ERROR'}")
    print(f"API: {'✅ OK' if api_success else '❌ ERROR' if api_success is False else '⚠️  No probado'}")
    
    if db_success:
        print("\n🎉 ¡Conexión con Supabase exitosa!")
        print("   Puedes ejecutar la aplicación con: python3 app_multiusuario.py")
    else:
        print("\n💡 Para solucionar el problema:")
        print("   1. Verifica tu archivo .env")
        print("   2. Asegúrate de que tu proyecto de Supabase esté activo")
        print("   3. Ejecuta el script SQL en Supabase si no lo has hecho")
        print("   4. Verifica tu conexión a internet")
