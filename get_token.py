#!/usr/bin/env python3
"""
Script para obtener token de autenticación para la API
"""

import requests
import json

def get_auth_token(username, password, base_url="http://localhost:5001"):
    """Obtener token de autenticación"""
    
    # Endpoint de login
    login_url = f"{base_url}/api/auth/login"
    
    # Datos de login
    login_data = {
        "username": username,
        "password": password
    }
    
    try:
        # Realizar login
        response = requests.post(login_url, json=login_data)
        
        if response.status_code == 200:
            data = response.json()
            token = data.get('token')
            user_id = data.get('user_id')
            username = data.get('username')
            
            print("✅ Login exitoso!")
            print(f"👤 Usuario: {username}")
            print(f"🆔 User ID: {user_id}")
            print(f"🔑 Token: {token}")
            print()
            print("📋 Para usar en Swagger:")
            print(f"   1. Ve a http://localhost:5001/swagger/")
            print(f"   2. Haz clic en 'Authorize' (🔒)")
            print(f"   3. Usa el token: {token}")
            print()
            print("📋 Para usar con curl:")
            print(f"   curl -H 'Authorization: Bearer {token}' \\")
            print(f"        http://localhost:5001/api/reports/results")
            
            return token
        else:
            print(f"❌ Error en login: {response.status_code}")
            print(f"   Respuesta: {response.text}")
            return None
            
    except requests.exceptions.ConnectionError:
        print("❌ Error: No se puede conectar al servidor")
        print("   Asegúrate de que la aplicación esté ejecutándose en http://localhost:5001")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def test_token(token, base_url="http://localhost:5001"):
    """Probar el token obtenido"""
    
    if not token:
        print("❌ No hay token para probar")
        return
    
    # Probar endpoint que requiere autenticación
    test_url = f"{base_url}/api/reports/options"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(test_url, headers=headers)
        
        if response.status_code == 200:
            print("✅ Token válido - API funcionando correctamente")
            data = response.json()
            print(f"📊 Opciones disponibles: {list(data.keys())}")
        else:
            print(f"⚠️  Token puede no ser válido: {response.status_code}")
            print(f"   Respuesta: {response.text}")
            
    except Exception as e:
        print(f"❌ Error probando token: {e}")

if __name__ == "__main__":
    print("🔐 Obtener Token de Autenticación - Poker Results API")
    print("=" * 60)
    
    # Solicitar credenciales
    username = input("👤 Usuario: ").strip()
    password = input("🔒 Contraseña: ").strip()
    
    if not username or not password:
        print("❌ Usuario y contraseña son requeridos")
        exit(1)
    
    print()
    print("🔄 Obteniendo token...")
    
    # Obtener token
    token = get_auth_token(username, password)
    
    if token:
        print()
        print("🧪 Probando token...")
        test_token(token)

