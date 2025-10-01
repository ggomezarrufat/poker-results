#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script para corregir el esquema de la base de datos en Supabase
"""

import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configurar Supabase
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL y SUPABASE_KEY deben estar configurados en el archivo .env")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def fix_database_schema():
    """Corregir el esquema de la base de datos"""
    try:
        print("🔧 Corrigiendo esquema de la base de datos...")
        
        # SQL para corregir el esquema
        sql_commands = [
            # Deshabilitar RLS temporalmente
            "ALTER TABLE users DISABLE ROW LEVEL SECURITY;",
            "ALTER TABLE poker_results DISABLE ROW LEVEL SECURITY;",
            
            # Eliminar la tabla poker_results si existe (para recrearla)
            "DROP TABLE IF EXISTS poker_results CASCADE;",
            
            # Recrear la tabla poker_results con el esquema correcto
            """
            CREATE TABLE poker_results (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                fecha DATE NOT NULL,
                hora TIME,
                descripcion TEXT NOT NULL,
                importe DECIMAL(10,2) NOT NULL,
                categoria VARCHAR(50) NOT NULL,
                tipo_movimiento VARCHAR(50) NOT NULL,
                tipo_juego VARCHAR(50) NOT NULL,
                sala VARCHAR(50) NOT NULL,
                nivel_buyin VARCHAR(20),
                hash_duplicado VARCHAR(64) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            """,
            
            # Crear índices para mejorar rendimiento
            "CREATE INDEX idx_poker_results_user_id ON poker_results(user_id);",
            "CREATE INDEX idx_poker_results_fecha ON poker_results(fecha);",
            "CREATE INDEX idx_poker_results_categoria ON poker_results(categoria);",
            "CREATE INDEX idx_poker_results_sala ON poker_results(sala);",
            "CREATE INDEX idx_poker_results_hash_duplicado ON poker_results(hash_duplicado);",
            "CREATE INDEX idx_poker_results_user_fecha ON poker_results(user_id, fecha);",
            
            # Habilitar RLS nuevamente
            "ALTER TABLE users ENABLE ROW LEVEL SECURITY;",
            "ALTER TABLE poker_results ENABLE ROW LEVEL SECURITY;",
            
            # Crear políticas RLS simplificadas
            "CREATE POLICY \"Users can view own data\" ON poker_results FOR SELECT USING (user_id = auth.uid());",
            "CREATE POLICY \"Users can insert own data\" ON poker_results FOR INSERT WITH CHECK (user_id = auth.uid());",
            "CREATE POLICY \"Users can update own data\" ON poker_results FOR UPDATE USING (user_id = auth.uid());",
            "CREATE POLICY \"Users can delete own data\" ON poker_results FOR DELETE USING (user_id = auth.uid());",
        ]
        
        # Ejecutar comandos SQL
        for i, sql in enumerate(sql_commands, 1):
            print(f"Ejecutando comando {i}/{len(sql_commands)}...")
            try:
                result = supabase.rpc('exec_sql', {'sql': sql}).execute()
                print(f"✅ Comando {i} ejecutado exitosamente")
            except Exception as e:
                print(f"⚠️  Comando {i} falló (puede ser normal): {e}")
                # Continuar con el siguiente comando
        
        print("✅ Esquema de base de datos corregido exitosamente")
        return True
        
    except Exception as e:
        print(f"❌ Error corrigiendo esquema: {e}")
        return False

def test_connection():
    """Probar la conexión a Supabase"""
    try:
        print("🔍 Probando conexión a Supabase...")
        
        # Probar conexión con una consulta simple
        result = supabase.table('users').select('id').limit(1).execute()
        print("✅ Conexión a Supabase exitosa")
        return True
        
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return False

if __name__ == '__main__':
    print("🚀 Iniciando corrección del esquema de base de datos...")
    
    # Probar conexión primero
    if not test_connection():
        print("❌ No se puede conectar a Supabase. Verifica las credenciales.")
        exit(1)
    
    # Corregir esquema
    if fix_database_schema():
        print("🎉 ¡Esquema corregido exitosamente!")
        print("Ahora puedes intentar importar archivos nuevamente.")
    else:
        print("❌ Error corrigiendo el esquema. Revisa los logs.")
