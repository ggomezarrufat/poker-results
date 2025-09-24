#!/usr/bin/env python3
"""
Script para inicializar la base de datos con usuario administrador
"""

import os
from app_multiusuario import app, db, User
from werkzeug.security import generate_password_hash

def init_database():
    """Inicializar la base de datos y crear usuario administrador"""
    with app.app_context():
        # Crear todas las tablas
        db.create_all()
        print("✅ Tablas creadas exitosamente")
        
        # Verificar si ya existe un usuario administrador
        admin_user = User.query.filter_by(is_admin=True).first()
        
        if not admin_user:
            # Crear usuario administrador por defecto
            admin = User(
                username='admin',
                email='admin@poker-results.com',
                is_admin=True,
                is_active=True
            )
            admin.set_password('admin123')  # Cambiar en producción
            
            db.session.add(admin)
            db.session.commit()
            
            print("✅ Usuario administrador creado:")
            print("   Usuario: admin")
            print("   Contraseña: admin123")
            print("   ⚠️  IMPORTANTE: Cambiar la contraseña en producción")
        else:
            print("✅ Usuario administrador ya existe")
        
        print("✅ Base de datos inicializada correctamente")

if __name__ == '__main__':
    init_database()
