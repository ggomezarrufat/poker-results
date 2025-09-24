#!/usr/bin/env python3

import requests
import json

# Obtener datos de la API
response = requests.get('http://localhost:9000/api/informes/resultados')
data = response.json()

print("=== NUEVAS ESTADÍSTICAS DE TORNEOS ===")
print(f"Total importe: ${data['estadisticas']['total_importe']:.2f}")
print(f"Cantidad torneos jugados: {data['estadisticas']['cantidad_torneos']}")
print(f"Total invertido: ${data['estadisticas']['total_invertido']:.2f}")
print(f"Total ganancias: ${data['estadisticas']['total_ganancias']:.2f}")
print(f"ROI: {data['estadisticas']['roi']:.1f}%")
print(f"Total registros: {data['estadisticas']['total_registros']}")

# Verificar cálculo del ROI
invertido = data['estadisticas']['total_invertido']
ganancias = data['estadisticas']['total_ganancias']
roi_calculado = ((ganancias - invertido) / invertido * 100) if invertido > 0 else 0
print(f"\nROI calculado manualmente: {roi_calculado:.1f}%")

# Análisis detallado de torneos
torneos = [r for r in data['resultados'] if r['categoria'] == 'Torneo']
egresos = [r for r in torneos if r['importe'] < 0]
ingresos = [r for r in torneos if r['importe'] > 0]

print(f"\n=== ANÁLISIS DETALLADO ===")
print(f"Registros de torneos: {len(torneos)}")
print(f"Egresos (inversiones): {len(egresos)}")
print(f"Ingresos (ganancias): {len(ingresos)}")

if egresos:
    total_egresos = sum(abs(r['importe']) for r in egresos)
    print(f"Total egresos calculado: ${total_egresos:.2f}")
    print(f"Promedio por egreso: ${total_egresos/len(egresos):.2f}")

if ingresos:
    total_ingresos = sum(r['importe'] for r in ingresos)
    print(f"Total ingresos calculado: ${total_ingresos:.2f}")
    print(f"Promedio por ingreso: ${total_ingresos/len(ingresos):.2f}")

# Verificar que el ROI es correcto
if invertido > 0:
    roi_verificado = ((ganancias - invertido) / invertido) * 100
    print(f"\nROI verificado: {roi_verificado:.1f}%")
    print(f"Diferencia con API: {abs(roi_verificado - data['estadisticas']['roi']):.6f}%")
