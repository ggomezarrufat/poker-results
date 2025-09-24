#!/usr/bin/env python3

import sqlite3
import os

# Conectar a la base de datos
db_path = '/Users/gga/Proyectos/poker-results/poker_results.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=== LIMPIANDO BASE DE DATOS ===")
# Eliminar todos los registros existentes
cursor.execute("DELETE FROM poker_result")
conn.commit()
print("✅ Base de datos limpiada")

# Cerrar conexión
conn.close()

print("\n=== REIMPORTANDO DATOS ===")
# Importar el archivo WPN con la nueva lógica
import requests

file_path = "/Users/gga/Proyectos/poker-results/uploads/WPN_Model.xlsx"
base_url = "http://localhost:9000"

files = {
    'archivo': ('WPN_Model.xlsx', open(file_path, 'rb'), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
}

data = {
    'sala': 'WPN'
}

try:
    response = requests.post(f"{base_url}/api/importar", files=files, data=data)
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Reimportación exitosa!")
        print(f"Registros importados: {result['resultados_importados']}")
        print(f"Duplicados omitidos: {result['duplicados_encontrados']}")
    else:
        print(f"❌ Error en la reimportación: {response.status_code}")
        print(f"Respuesta: {response.text}")
        
except Exception as e:
    print(f"❌ Error: {e}")
finally:
    files['archivo'][1].close()

print("\n=== VERIFICANDO NUEVOS TIPOS DE JUEGO ===")
# Verificar los tipos de juego después de la reimportación
response = requests.get(f"{base_url}/api/informes/opciones")
if response.status_code == 200:
    opciones = response.json()
    print("Tipos de juego disponibles:")
    for tipo in opciones['tipos_juego']:
        print(f"  - {tipo}")
else:
    print("Error al obtener opciones")
