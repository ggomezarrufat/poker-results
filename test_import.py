#!/usr/bin/env python3
"""
Script para probar la importación directamente
"""

import pandas as pd
from app import app, db, PokerResult, procesar_archivo_wpn

def test_import():
    """Prueba la importación directamente"""
    with app.app_context():
        print("=== PROBANDO IMPORTACIÓN DIRECTA ===")
        
        # Verificar archivo
        file_path = 'uploads/WPN_Model.xlsx'
        try:
            df = pd.read_excel(file_path)
            print(f"✅ Archivo leído: {len(df)} registros")
            print(f"Columnas: {list(df.columns)}")
            print(f"Primeras 3 filas:")
            print(df.head(3))
            
            # Probar procesamiento
            print("\n=== PROCESANDO ARCHIVO ===")
            resultados_importados, duplicados_encontrados, duplicados_detalle = procesar_archivo_wpn(file_path)
            
            print(f"Resultados importados: {resultados_importados}")
            print(f"Duplicados encontrados: {duplicados_encontrados}")
            print(f"Detalles de duplicados: {len(duplicados_detalle)}")
            
            # Verificar base de datos
            total = PokerResult.query.count()
            print(f"Total en BD: {total}")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    test_import()