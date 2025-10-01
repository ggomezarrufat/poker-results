#!/usr/bin/env python3
"""
Script para probar los cambios en la página principal después del login
"""

import requests
import sys
import re

def test_page_changes():
    """Probar cambios en la página principal"""
    base_url = "http://localhost:5001"
    
    # Crear sesión
    session = requests.Session()
    
    print("🔐 Haciendo login...")
    
    # Obtener página de login para obtener CSRF token
    login_page = session.get(f"{base_url}/login")
    if login_page.status_code != 200:
        print(f"❌ Error obteniendo página de login: {login_page.status_code}")
        return False
    
    # Buscar CSRF token en el HTML
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
        
        # Verificar que NO estén las características eliminadas
        caracteristicas_eliminadas = [
            "Características Principales",
            "Base de Datos Local",
            "Control de Duplicados", 
            "Filtros Avanzados"
        ]
        
        for caracteristica in caracteristicas_eliminadas:
            if caracteristica in login_response.text:
                print(f"❌ ERROR: '{caracteristica}' aún está presente")
                return False
            else:
                print(f"✅ '{caracteristica}' eliminada correctamente")
        
        # Verificar que estén las secciones que deben permanecer
        secciones_requeridas = [
            "Importar Resultados",
            "Generar Informes", 
            "Análisis Avanzado",
            "Zona de Peligro"
        ]
        
        for seccion in secciones_requeridas:
            if seccion in login_response.text:
                print(f"✅ '{seccion}' presente correctamente")
            else:
                print(f"❌ ERROR: '{seccion}' no encontrada")
                return False
        
        print("\n🎉 ¡Todos los cambios se aplicaron correctamente!")
        return True
    else:
        print("❌ No se redirigió a la página principal")
        print(f"Título de la página: {re.search(r'<title>(.*?)</title>', login_response.text).group(1) if re.search(r'<title>(.*?)</title>', login_response.text) else 'No encontrado'}")
        return False

if __name__ == "__main__":
    test_page_changes()

