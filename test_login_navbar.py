#!/usr/bin/env python3
"""
Script para probar el login y verificar el navbar con usuario logueado
"""

import requests
import sys

def test_login_and_navbar():
    """Probar login y verificar navbar"""
    base_url = "http://localhost:5001"
    
    # Crear sesión
    session = requests.Session()
    
    print("🔐 Probando login...")
    
    # Obtener página de login para obtener CSRF token
    login_page = session.get(f"{base_url}/login")
    if login_page.status_code != 200:
        print(f"❌ Error obteniendo página de login: {login_page.status_code}")
        return False
    
    # Buscar CSRF token en el HTML
    import re
    csrf_match = re.search(r'name="csrf_token".*?value="([^"]+)"', login_page.text)
    if not csrf_match:
        print("❌ No se encontró CSRF token")
        return False
    
    csrf_token = csrf_match.group(1)
    print(f"✅ CSRF token obtenido: {csrf_token[:20]}...")
    
    # Hacer login
    login_data = {
        'username': 'admin',
        'password': 'admin123',
        'csrf_token': csrf_token,
        'remember_me': 'y'
    }
    
    login_response = session.post(f"{base_url}/login", data=login_data, allow_redirects=True)
    
    if login_response.status_code != 200:
        print(f"❌ Error en login: {login_response.status_code}")
        return False
    
    print("✅ Login exitoso")
    
    # Verificar si estamos en la página principal
    if "Poker Results Analyzer" in login_response.text:
        print("✅ Redirigido a página principal")
        
        # Buscar información del usuario en el navbar
        if 'current_user.username' in login_response.text:
            print("✅ Usuario encontrado en navbar")
        else:
            print("❌ Usuario NO encontrado en navbar")
            
        # Buscar dropdown del usuario
        if 'dropdown-toggle' in login_response.text and 'admin' in login_response.text:
            print("✅ Dropdown del usuario encontrado")
        else:
            print("❌ Dropdown del usuario NO encontrado")
            
        # Mostrar parte del navbar
        import re
        navbar_match = re.search(r'<nav class="navbar[^>]*>.*?</nav>', login_response.text, re.DOTALL)
        if navbar_match:
            navbar_html = navbar_match.group(0)
            print("\n📋 Navbar encontrado:")
            print(navbar_html[:500] + "..." if len(navbar_html) > 500 else navbar_html)
        else:
            print("❌ Navbar no encontrado")
    else:
        print("❌ No se redirigió a la página principal")
        print(f"Título de la página: {re.search(r'<title>(.*?)</title>', login_response.text).group(1) if re.search(r'<title>(.*?)</title>', login_response.text) else 'No encontrado'}")
    
    return True

if __name__ == "__main__":
    test_login_and_navbar()

