#!/usr/bin/env python3

import sqlite3
import os

print("=== LIMPIANDO BASE DE DATOS ===")

# Conectar a la base de datos
db_path = '/Users/gga/Proyectos/poker-results/poker_results.db'

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Verificar tablas existentes
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(f"Tablas encontradas: {[t[0] for t in tables]}")
    
    # Eliminar todos los registros de la tabla poker_result
    try:
        cursor.execute("DELETE FROM poker_result")
        conn.commit()
        print("✅ Todos los registros eliminados de poker_result")
    except sqlite3.OperationalError as e:
        print(f"❌ Error eliminando registros: {e}")
        # Intentar con el nombre correcto de la tabla
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        if tables:
            table_name = tables[0][0]
            print(f"Intentando con tabla: {table_name}")
            cursor.execute(f"DELETE FROM {table_name}")
            conn.commit()
            print(f"✅ Todos los registros eliminados de {table_name}")
    
    # Verificar que la tabla esté vacía
    cursor.execute("SELECT COUNT(*) FROM poker_result")
    count = cursor.fetchone()[0]
    print(f"Registros restantes: {count}")
    
    conn.close()
    print("✅ Base de datos limpiada exitosamente")
else:
    print("❌ Base de datos no encontrada")

print("\n=== INSTRUCCIONES ===")
print("1. La base de datos ha sido limpiada")
print("2. Ahora puedes reimportar tus archivos WPN")
print("3. Los tipos de movimiento se extraerán directamente de Payment Method")
print("4. Ve a http://localhost:9000/importar para reimportar")
