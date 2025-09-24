#!/usr/bin/env python3

import requests
import json

# Obtener datos de la API
response = requests.get('http://localhost:9000/api/informes/resultados')
data = response.json()

print("=== ANÁLISIS DE TORNEOS JUGADOS ===")
print(f"Total registros: {data['estadisticas']['total_registros']}")
print(f"Total importe: ${data['estadisticas']['total_importe']:.2f}")
print(f"Cantidad torneos (Buy-in + Torneo): {data['estadisticas']['cantidad_torneos']}")

# Analizar los torneos jugados
buy_ins_torneo = [r for r in data['resultados'] if r['tipo_movimiento'] == 'Buy-in' and r['categoria'] == 'Torneo']
print(f"\nRegistros Buy-in + Torneo encontrados: {len(buy_ins_torneo)}")

if buy_ins_torneo:
    print("\n=== PRIMEROS 5 TORNEOS JUGADOS ===")
    for i, torneo in enumerate(buy_ins_torneo[:5]):
        print(f"{i+1}. {torneo['fecha']} - {torneo['descripcion']} - ${torneo['importe']:.2f} - {torneo['tipo_juego']}")
    
    # Calcular estadísticas de torneos
    importes_torneos = [t['importe'] for t in buy_ins_torneo]
    total_torneos = sum(importes_torneos)
    promedio_torneo = total_torneos / len(importes_torneos) if importes_torneos else 0
    
    print(f"\n=== ESTADÍSTICAS DE TORNEOS ===")
    print(f"Total invertido en torneos: ${total_torneos:.2f}")
    print(f"Promedio por torneo: ${promedio_torneo:.2f}")
    print(f"Torneo más caro: ${max(importes_torneos):.2f}")
    print(f"Torneo más barato: ${min(importes_torneos):.2f}")

# Verificar otros tipos de movimiento en torneos
print(f"\n=== TIPOS DE MOVIMIENTO EN TORNEOS ===")
tipos_en_torneos = {}
for r in data['resultados']:
    if r['categoria'] == 'Torneo':
        tipo = r['tipo_movimiento']
        tipos_en_torneos[tipo] = tipos_en_torneos.get(tipo, 0) + 1

for tipo, count in sorted(tipos_en_torneos.items()):
    print(f"{tipo}: {count} registros")
