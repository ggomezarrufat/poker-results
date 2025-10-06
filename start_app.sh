#!/bin/bash

# Script para iniciar la aplicación Poker Results
# Autor: Sistema de gestión de resultados de poker
# Fecha: $(date +%Y-%m-%d)

echo "🚀 Iniciando aplicación Poker Results..."
echo "========================================"

# Verificar si estamos en el directorio correcto
if [ ! -f "app_multiusuario_working.py" ]; then
    echo "❌ Error: No se encontró app_multiusuario_working.py"
    echo "   Asegúrate de ejecutar este script desde el directorio del proyecto"
    exit 1
fi

# Verificar si existe el entorno virtual
if [ ! -d "venv" ]; then
    echo "❌ Error: No se encontró el entorno virtual 'venv'"
    echo "   Crea el entorno virtual con: python -m venv venv"
    exit 1
fi

# Verificar si existe el archivo .env
if [ ! -f ".env" ]; then
    echo "❌ Error: No se encontró el archivo .env"
    echo "   Copia env.example a .env y configura las variables de Supabase"
    exit 1
fi

# Activar entorno virtual
echo "📦 Activando entorno virtual..."
source venv/bin/activate

# Verificar que las dependencias estén instaladas
echo "🔍 Verificando dependencias..."
python -c "import flask, supabase, pandas, werkzeug" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "📥 Instalando dependencias..."
    pip install -r requirements.txt
fi

# Verificar conexión a Supabase
echo "🌐 Verificando conexión a Supabase..."
python -c "
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_KEY')

if not url or not key:
    print('❌ Variables de entorno de Supabase no configuradas')
    exit(1)

try:
    supabase = create_client(url, key)
    # Intentar una consulta simple
    result = supabase.table('users').select('id').limit(1).execute()
    print('✅ Conexión a Supabase exitosa')
except Exception as e:
    print(f'❌ Error conectando a Supabase: {e}')
    exit(1)
"

if [ $? -ne 0 ]; then
    echo "   Revisa la configuración de SUPABASE_URL y SUPABASE_KEY en .env"
    exit 1
fi

# Iniciar la aplicación
echo ""
echo "✅ Todo listo. Iniciando aplicación..."
echo "📍 La aplicación estará disponible en: http://localhost:5001"
echo "🛑 Presiona Ctrl+C para detener la aplicación"
echo "========================================"

# Ejecutar la aplicación
python app_multiusuario_working.py

