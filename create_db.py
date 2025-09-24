#!/usr/bin/env python3
"""
Script para crear la base de datos con el nuevo esquema
"""

import os
from app import app, db

def create_database():
    with app.app_context():
        # Asegurarse de que la carpeta 'instance' exista
        instance_path = os.path.join(app.root_path, 'instance')
        os.makedirs(instance_path, exist_ok=True)
        
        # Crear todas las tablas
        db.create_all()
        print("✅ Base de datos creada exitosamente con el nuevo esquema")

if __name__ == '__main__':
    print("Creando nueva base de datos...")
    create_database()
