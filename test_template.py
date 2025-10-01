#!/usr/bin/env python3
"""
Script para probar el template directamente
"""

from flask import Flask, render_template
import os

# Crear una aplicación Flask de prueba
app = Flask(__name__)
app.config['SECRET_KEY'] = 'test-key'
app.config['SERVER_NAME'] = 'localhost:5001'
app.config['APPLICATION_ROOT'] = '/'
app.config['PREFERRED_URL_SCHEME'] = 'http'

if __name__ == '__main__':
    print("🧪 Probando template directamente...")
    with app.app_context():
        try:
            html = render_template('index.html')
            print("✅ Template renderizado correctamente")
            
            if "Características Principales" in html:
                print("❌ ERROR: 'Características Principales' encontrada en el template")
                print("📋 Contexto:")
                import re
                pattern = r'.{0,200}Características Principales.{0,200}'
                match = re.search(pattern, html, re.DOTALL)
                if match:
                    print(match.group(0))
            else:
                print("✅ 'Características Principales' NO encontrada en el template")
            
            if "Zona de Peligro" in html:
                print("✅ 'Zona de Peligro' encontrada correctamente")
            else:
                print("❌ ERROR: 'Zona de Peligro' NO encontrada")
                
        except Exception as e:
            print(f"❌ Error renderizando template: {e}")
