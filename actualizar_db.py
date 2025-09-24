#!/usr/bin/env python3
"""
Script para actualizar la base de datos con la nueva columna 'hora'
"""

import os
import sqlite3
from app import app, db

def actualizar_base_datos():
    """Actualiza la base de datos agregando la columna hora"""
    with app.app_context():
        print("=== ACTUALIZANDO BASE DE DATOS ===")
        
        # Verificar si la columna ya existe
        conn = sqlite3.connect('poker_results.db')
        cursor = conn.cursor()
        
        # Obtener información de la tabla
        cursor.execute("PRAGMA table_info(poker_result)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        print(f"Columnas actuales: {column_names}")
        
        if 'hora' not in column_names:
            print("Agregando columna 'hora'...")
            cursor.execute("ALTER TABLE poker_result ADD COLUMN hora TIME")
            conn.commit()
            print("✅ Columna 'hora' agregada exitosamente")
        else:
            print("✅ Columna 'hora' ya existe")
        
        conn.close()
        
        # Recrear la tabla con el nuevo modelo
        print("Recreando tabla con nuevo modelo...")
        db.drop_all()
        db.create_all()
        print("✅ Tabla recreada con nuevo modelo")

if __name__ == '__main__':
    actualizar_base_datos()
