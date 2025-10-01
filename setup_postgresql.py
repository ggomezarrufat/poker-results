#!/usr/bin/env python3
"""
Script para configurar la base de datos PostgreSQL
"""

import os
from app_swagger import app, db, User
from werkzeug.security import generate_password_hash

def setup_database():
    """Configurar la base de datos PostgreSQL"""
    
    print("🔧 Configurando Base de Datos PostgreSQL...")
    print("=" * 50)
    
    with app.app_context():
        try:
            # Crear todas las tablas
            print("📋 Creando tablas...")
            db.create_all()
            print("✅ Tablas creadas exitosamente")
            
            # Verificar si ya existen usuarios
            existing_users = User.query.count()
            print(f"👥 Usuarios existentes: {existing_users}")
            
            if existing_users == 0:
                print("🔨 Creando usuarios de prueba...")
                
                # Crear usuario administrador
                admin_user = User(
                    username='admin',
                    email='admin@example.com',
                    password_hash=generate_password_hash('admin123', method='pbkdf2:sha256'),
                    is_admin=True,
                    is_active=True
                )
                db.session.add(admin_user)
                
                # Crear usuario de prueba
                test_user = User(
                    username='testuser',
                    email='test@example.com',
                    password_hash=generate_password_hash('testpass123', method='pbkdf2:sha256'),
                    is_admin=True,
                    is_active=True
                )
                db.session.add(test_user)
                
                # Crear usuario demo
                demo_user = User(
                    username='demo',
                    email='demo@example.com',
                    password_hash=generate_password_hash('demo123', method='pbkdf2:sha256'),
                    is_admin=False,
                    is_active=True
                )
                db.session.add(demo_user)
                
                # Confirmar cambios
                db.session.commit()
                print("✅ Usuarios creados exitosamente")
                
                # Mostrar usuarios creados
                print("\n👥 Usuarios disponibles:")
                users = User.query.all()
                for user in users:
                    print(f"  - {user.username} / (contraseña en la base de datos)")
                    print(f"    ID: {user.id}")
                    print(f"    Email: {user.email}")
                    print(f"    Admin: {user.is_admin}")
                    print()
            else:
                print("⚠️ Ya existen usuarios en la base de datos")
                print("👥 Usuarios actuales:")
                users = User.query.all()
                for user in users:
                    print(f"  - {user.username} (ID: {user.id})")
            
            print("🎉 Configuración completada exitosamente!")
            
        except Exception as e:
            print(f"❌ Error configurando la base de datos: {e}")
            return False
    
    return True

def test_connection():
    """Probar la conexión a la base de datos"""
    
    print("🔍 Probando conexión a PostgreSQL...")
    
    try:
        with app.app_context():
            # Probar consulta simple
            result = db.session.execute(db.text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"✅ Conexión exitosa a PostgreSQL")
            print(f"📊 Versión: {version}")
            
            # Probar consulta a usuarios
            user_count = User.query.count()
            print(f"👥 Usuarios en la base de datos: {user_count}")
            
            return True
            
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Configurador de Base de Datos PostgreSQL")
    print("=" * 50)
    
    # Verificar variable de entorno
    if not os.environ.get('DATABASE_URL'):
        print("❌ Error: DATABASE_URL no está configurado")
        print("💡 Configura la variable de entorno:")
        print("   export DATABASE_URL='postgresql://user:password@host:port/database'")
        exit(1)
    
    # Probar conexión
    if not test_connection():
        print("❌ No se pudo conectar a la base de datos")
        exit(1)
    
    # Configurar base de datos
    if setup_database():
        print("\n🎉 ¡Base de datos configurada correctamente!")
        print("🔗 Ahora puedes ejecutar la aplicación:")
        print("   python app_swagger.py")
    else:
        print("\n❌ Error configurando la base de datos")
        exit(1)

