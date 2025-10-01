#!/usr/bin/env python3
"""
Script para probar el endpoint de login de la API
"""

import requests
import json

def test_login_api():
    """Probar el endpoint de login"""
    
    base_url = "http://localhost:5001"
    login_url = f"{base_url}/api/auth/login"
    
    # Credenciales de prueba
    credentials = {
        "username": "testuser",
        "password": "testpass123"
    }
    
    print("🔐 Probando Endpoint de Login - Poker Results API")
    print("=" * 60)
    print(f"📍 URL: {login_url}")
    print(f"👤 Usuario: {credentials['username']}")
    print()
    
    try:
        # Realizar login
        print("🔄 Enviando request de login...")
        response = requests.post(login_url, json=credentials)
        
        print(f"📊 Status Code: {response.status_code}")
        print(f"📋 Headers: {dict(response.headers)}")
        print()
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Login exitoso!")
            print(f"👤 Usuario: {data.get('username')}")
            print(f"🆔 User ID: {data.get('user_id')}")
            print(f"🔑 Token: {data.get('token')}")
            print()
            
            # Probar el token con otro endpoint
            token = data.get('token')
            if token:
                print("🧪 Probando token con endpoint protegido...")
                test_protected_endpoint(token, base_url)
            
        else:
            print(f"❌ Error en login: {response.status_code}")
            print(f"📄 Respuesta: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Error: No se puede conectar al servidor")
        print("   Asegúrate de que la aplicación esté ejecutándose en http://localhost:5001")
    except Exception as e:
        print(f"❌ Error: {e}")

def test_protected_endpoint(token, base_url):
    """Probar un endpoint que requiere autenticación"""
    
    # Probar endpoint de opciones
    options_url = f"{base_url}/api/reports/options"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(options_url, headers=headers)
        
        if response.status_code == 200:
            print("✅ Token válido - Endpoint protegido accesible")
            data = response.json()
            print(f"📊 Opciones disponibles: {list(data.keys())}")
        elif response.status_code == 302:
            print("⚠️  Redirección a login - Token puede no ser válido")
        else:
            print(f"⚠️  Error accediendo endpoint protegido: {response.status_code}")
            print(f"📄 Respuesta: {response.text}")
            
    except Exception as e:
        print(f"❌ Error probando endpoint protegido: {e}")

def test_with_curl():
    """Mostrar comandos curl para usar desde Allin"""
    
    print("\n" + "=" * 60)
    print("📋 Comandos para usar desde Allin:")
    print("=" * 60)
    
    print("\n1️⃣  Login para obtener token:")
    print("curl -X POST http://localhost:5001/api/auth/login \\")
    print("  -H 'Content-Type: application/json' \\")
    print("  -d '{\"username\": \"testuser\", \"password\": \"testpass123\"}'")
    
    print("\n2️⃣  Usar token en endpoint protegido:")
    print("curl -H 'Authorization: Bearer TOKEN_AQUI' \\")
    print("     http://localhost:5001/api/reports/results")
    
    print("\n3️⃣  Obtener opciones de filtros:")
    print("curl -H 'Authorization: Bearer TOKEN_AQUI' \\")
    print("     http://localhost:5001/api/reports/options")

if __name__ == "__main__":
    test_login_api()
    test_with_curl()

