#!/usr/bin/env python3
"""
Script para debuggear la página principal
"""

import requests
import re

def debug_page():
    """Debuggear la página principal"""
    base_url = "http://localhost:5001"
    
    # Crear sesión
    session = requests.Session()
    
    print("🔐 Haciendo login...")
    
    # Obtener página de login para obtener CSRF token
    login_page = session.get(f"{base_url}/login")
    csrf_match = re.search(r'name="csrf_token".*?value="([^"]+)"', login_page.text)
    csrf_token = csrf_match.group(1)
    
    # Hacer login
    login_data = {
        'username': 'admin',
        'password': 'admin123',
        'csrf_token': csrf_token,
        'remember_me': 'y'
    }
    
    login_response = session.post(f"{base_url}/login", data=login_data, allow_redirects=True)
    
    # Guardar la respuesta HTML para analizarla
    with open('/Users/gga/Proyectos/poker-results/debug_response.html', 'w', encoding='utf-8') as f:
        f.write(login_response.text)
    
    print("✅ Respuesta HTML guardada en debug_response.html")
    
    # Buscar la sección de características
    if "Características Principales" in login_response.text:
        print("❌ 'Características Principales' encontrada en la respuesta")
        
        # Buscar el contexto alrededor de esa sección
        pattern = r'.{0,200}Características Principales.{0,200}'
        match = re.search(pattern, login_response.text, re.DOTALL)
        if match:
            print("📋 Contexto encontrado:")
            print(match.group(0))
    else:
        print("✅ 'Características Principales' NO encontrada en la respuesta")
    
    # Buscar otras secciones
    secciones = ["Importar Resultados", "Generar Informes", "Análisis Avanzado", "Zona de Peligro"]
    for seccion in secciones:
        if seccion in login_response.text:
            print(f"✅ '{seccion}' encontrada")
        else:
            print(f"❌ '{seccion}' NO encontrada")

if __name__ == "__main__":
    debug_page()

