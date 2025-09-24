#!/usr/bin/env python3

import pandas as pd
import os

def analizar_archivo_wpn():
    """Analiza el archivo WPN para entender por qué se pierden registros"""
    
    # Buscar archivo WPN
    archivos_wpn = []
    for root, dirs, files in os.walk('/Users/gga/Proyectos/poker-results'):
        for file in files:
            if 'WPN' in file and file.endswith(('.xlsx', '.xls')):
                archivos_wpn.append(os.path.join(root, file))
    
    if not archivos_wpn:
        print("❌ No se encontró archivo WPN")
        return
    
    archivo_path = archivos_wpn[0]
    print(f"📁 Analizando archivo: {archivo_path}")
    
    try:
        # Leer archivo
        df = pd.read_excel(archivo_path)
        print(f"📊 Total registros en archivo: {len(df)}")
        
        # Analizar columnas
        print(f"📋 Columnas: {list(df.columns)}")
        
        # Analizar fechas
        print(f"\n📅 ANÁLISIS DE FECHAS:")
        fechas_nulas = df['Date'].isna().sum()
        print(f"Registros sin fecha: {fechas_nulas}")
        
        if fechas_nulas > 0:
            print("Primeros registros sin fecha:")
            sin_fecha = df[df['Date'].isna()]
            for i, row in sin_fecha.head(3).iterrows():
                print(f"  Fila {i}: {row.to_dict()}")
        
        # Analizar formato de fechas
        print(f"\n🔍 ANÁLISIS DE FORMATO DE FECHAS:")
        fechas_validas = df.dropna(subset=['Date'])
        print(f"Registros con fecha: {len(fechas_validas)}")
        
        if len(fechas_validas) > 0:
            print("Primeras 3 fechas:")
            for i, fecha in enumerate(fechas_validas['Date'].head(3)):
                print(f"  {i+1}. {fecha} (tipo: {type(fecha)})")
        
        # Analizar Money In/Out
        print(f"\n💰 ANÁLISIS DE IMPORTES:")
        money_in_nulos = df['Money In'].isna().sum()
        money_out_nulos = df['Money Out'].isna().sum()
        print(f"Money In nulos: {money_in_nulos}")
        print(f"Money Out nulos: {money_out_nulos}")
        
        # Analizar Payment Method
        print(f"\n🏷️ ANÁLISIS DE PAYMENT METHOD:")
        payment_methods = df['Payment Method'].value_counts()
        print("Tipos de Payment Method:")
        for metodo, count in payment_methods.items():
            print(f"  {metodo}: {count}")
        
        # Simular procesamiento
        print(f"\n⚙️ SIMULACIÓN DE PROCESAMIENTO:")
        df_limpio = df.dropna(subset=['Date'])
        print(f"Después de eliminar fechas nulas: {len(df_limpio)}")
        
        errores_fecha = 0
        for index, row in df_limpio.iterrows():
            try:
                fecha_str = str(row['Date'])
                pd.to_datetime(fecha_str, format='%H:%M:%S %Y-%m-%d').date()
            except Exception as e:
                errores_fecha += 1
                if errores_fecha <= 3:  # Mostrar solo los primeros 3 errores
                    print(f"  Error en fila {index}: {e}")
                    print(f"    Fecha: {row['Date']}")
        
        print(f"Errores de formato de fecha: {errores_fecha}")
        print(f"Registros que se procesarían: {len(df_limpio) - errores_fecha}")
        
    except Exception as e:
        print(f"❌ Error analizando archivo: {e}")

if __name__ == "__main__":
    analizar_archivo_wpn()
