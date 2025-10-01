#!/usr/bin/env python3
"""
Script para crear un usuario de prueba
"""

import sys
import os
sys.path.append('.')

from app_multiusuario import app, db, User
from werkzeug.security import generate_password_hash

def create_test_user():
    """Crear usuario de prueba"""
    
    with app.app_context():
        # Crear tablas si no existen
        db.create_all()
        
        # Verificar si ya existe un usuario
        existing_user = User.query.filter_by(username='testuser').first()
        if existing_user:
            print("✅ Usuario 'testuser' ya existe")
            print(f"   ID: {existing_user.id}")
            print(f"   Email: {existing_user.email}")
            return existing_user
        
        # Crear nuevo usuario de prueba
        test_user = User(
            username='testuser',
            email='test@example.com',
            is_active=True,
            is_admin=True  # Hacer admin para pruebas
        )
        test_user.set_password('testpass123')
        
        try:
            db.session.add(test_user)
            db.session.commit()
            
            print("✅ Usuario de prueba creado exitosamente")
            print(f"   Usuario: testuser")
            print(f"   Contraseña: testpass123")
            print(f"   Email: test@example.com")
            print(f"   Admin: Sí")
            print()
            print("🔐 Credenciales para usar en Swagger:")
            print("   Usuario: testuser")
            print("   Contraseña: testpass123")
            
            return test_user
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error creando usuario: {e}")
            return None

if __name__ == "__main__":
    print("👤 Creando Usuario de Prueba - Poker Results API")
    print("=" * 50)
    
    create_test_user()
