#!/usr/bin/env python3
"""
Script para probar que los endpoints faltantes ahora están disponibles
"""

import requests
import json

def test_endpoints():
    """Probar que los endpoints están disponibles"""

    # Probar endpoint de debug (debería funcionar sin autenticación)
    try:
        response = requests.get('http://localhost:5001/api/debug/test', timeout=5)
        print(f"✅ Endpoint /api/debug/test: {response.status_code}")
        print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"❌ Error en /api/debug/test: {e}")

    # Probar endpoint de previsualización (espera error 401 por falta de autenticación)
    try:
        response = requests.post('http://localhost:5001/api/previsualizar-archivo',
                               data={'sala': 'WPN'}, timeout=5)
        print(f"✅ Endpoint /api/previsualizar-archivo: {response.status_code}")
        if response.status_code == 401:
            print("   ✅ Correcto - requiere autenticación")
        elif response.status_code == 404:
            print("   ❌ Endpoint no encontrado")
        else:
            print(f"   Response: {response.text[:200]}...")
    except Exception as e:
        print(f"❌ Error en /api/previsualizar-archivo: {e}")

    # Probar endpoint de importar-progreso (espera error 401 por falta de autenticación)
    try:
        response = requests.post('http://localhost:5001/api/importar-progreso',
                               data={'sala': 'WPN'}, timeout=5)
        print(f"✅ Endpoint /api/importar-progreso: {response.status_code}")
        if response.status_code == 401:
            print("   ✅ Correcto - requiere autenticación")
        elif response.status_code == 404:
            print("   ❌ Endpoint no encontrado")
        else:
            print(f"   Response: {response.text[:200]}...")
    except Exception as e:
        print(f"❌ Error en /api/importar-progreso: {e}")

    print("\n🔍 Prueba completada. Los endpoints deberían estar disponibles.")
    print("   Si ves errores 404, significa que los endpoints no están registrados.")
    print("   Si ves errores 401, significa que los endpoints están disponibles pero requieren autenticación.")

if __name__ == '__main__':
    test_endpoints()

