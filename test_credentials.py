#!/usr/bin/env python3
"""
Script para probar diferentes credenciales y ver cuáles funcionan
"""

import requests
import json

def test_credentials():
    """Probar diferentes credenciales"""
    
    base_url = "http://localhost:5001"
    login_url = f"{base_url}/api/auth/login"
    
    # Lista de credenciales a probar
    credentials_list = [
        {"username": "testuser", "password": "testpass123"},
        {"username": "admin", "password": "admin123"},
        {"username": "admin", "password": "admin"},
        {"username": "testuser", "password": "testpass"},
        {"username": "user", "password": "password"},
        {"username": "test", "password": "test"},
    ]
    
    print("🔐 Probando Credenciales - Poker Results API")
    print("=" * 60)
    
    for i, credentials in enumerate(credentials_list, 1):
        print(f"\n{i}. Probando: {credentials['username']} / {credentials['password']}")
        
        try:
            response = requests.post(login_url, json=credentials)
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ ÉXITO - Login exitoso")
                print(f"   👤 Usuario: {data.get('username')}")
                print(f"   🆔 User ID: {data.get('user_id')}")
                print(f"   🔑 Token: {data.get('token')[:20]}...")
            elif response.status_code == 401:
                print(f"   ❌ FALLO - Credenciales inválidas")
            else:
                print(f"   ⚠️  ERROR - Status: {response.status_code}")
                print(f"   📄 Respuesta: {response.text}")
                
        except requests.exceptions.ConnectionError:
            print(f"   ❌ ERROR - No se puede conectar al servidor")
            break
        except Exception as e:
            print(f"   ❌ ERROR - {e}")

def test_specific_credentials(username, password):
    """Probar credenciales específicas"""
    
    base_url = "http://localhost:5001"
    login_url = f"{base_url}/api/auth/login"
    
    print(f"🔐 Probando Credenciales Específicas")
    print("=" * 60)
    print(f"👤 Usuario: {username}")
    print(f"🔑 Contraseña: {password}")
    print()
    
    try:
        response = requests.post(login_url, json={"username": username, "password": password})
        
        print(f"📊 Status Code: {response.status_code}")
        print(f"📋 Headers: {dict(response.headers)}")
        print()
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Login exitoso!")
            print(f"👤 Usuario: {data.get('username')}")
            print(f"🆔 User ID: {data.get('user_id')}")
            print(f"🔑 Token: {data.get('token')}")
            return data.get('token')
        else:
            print(f"❌ Error en login: {response.status_code}")
            print(f"📄 Respuesta: {response.text}")
            return None
            
    except requests.exceptions.ConnectionError:
        print("❌ Error: No se puede conectar al servidor")
        print("   Asegúrate de que la aplicación esté ejecutándose en http://localhost:5001")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

if __name__ == "__main__":
    # Probar todas las credenciales comunes
    test_credentials()
    
    print("\n" + "=" * 60)
    print("💡 Si ninguna credencial funciona, prueba con:")
    print("   Usuario: testuser")
    print("   Contraseña: testpass123")
    print("=" * 60)

