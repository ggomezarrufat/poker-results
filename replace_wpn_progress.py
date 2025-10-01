#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Script para reemplazar la función procesar_archivo_wpn_con_progreso incorrecta

# Leer el archivo
with open('app_working.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Función correcta
funcion_correcta = '''def procesar_archivo_wpn_con_progreso(filepath, user_id, progress_callback):
    """Procesa archivos Excel de WPN con callback de progreso para SSE - VERSIÓN CORRECTA"""
    try:
        # Leer el archivo Excel
        df = pd.read_excel(filepath)
        print(f"Total registros en archivo: {len(df)}")
        
        # Limpiar y procesar los datos
        df_original = len(df)
        df = df.dropna(subset=['Date'])  # Eliminar filas sin fecha
        df_sin_fecha = df_original - len(df)
        print(f"Registros eliminados por falta de fecha: {df_sin_fecha}")
        
        total_registros = len(df)
        print(f"Procesando {total_registros} registros...")
        
        # Enviar total de registros al cliente
        progress_callback(f"data: {json.dumps({'tipo': 'inicio', 'total_registros': total_registros})}\\n\\n")
        
        resultados_importados = 0
        duplicados_encontrados = 0
        errores_procesamiento = 0
        duplicados_detalle = []
        registros_nuevos = []
        
        for index, row in df.iterrows():
            try:
                # Mostrar progreso cada 50 registros
                if (index + 1) % 50 == 0 or (index + 1) == total_registros:
                    porcentaje = ((index + 1) / total_registros) * 100
                    print(f"Progreso: {index + 1}/{total_registros} registros procesados ({porcentaje:.1f}%)")
                    
                    # Enviar progreso al cliente
                    progress_callback(f"data: {json.dumps({'tipo': 'progreso', 'procesados': index + 1, 'total': total_registros, 'porcentaje': porcentaje})}\\n\\n")
                
                # Procesar fecha y hora - WPN usa formato "HH:MM:SS YYYY-MM-DD"
                fecha_str = str(row['Date'])
                # Convertir formato "01:06:07 2025-09-24" a datetime
                fecha_hora = pd.to_datetime(fecha_str, format='%H:%M:%S %Y-%m-%d')
                fecha = fecha_hora.date()
                hora = fecha_hora.time()
                
                # Obtener valores originales para el hash
                money_in = float(row['Money In'])
                money_out = float(row['Money Out'])
                payment_method = str(row['Payment Method'])
                descripcion = str(row['Description'])
                
                # Determinar importe (Money In - Money Out)
                importe = money_in - money_out
                
                # Categorizar automáticamente usando la lógica original probada
                categoria, tipo_movimiento, tipo_juego = categorizar_movimiento(
                    payment_method, 
                    descripcion,
                    money_in,
                    money_out
                )
                
                # Generar hash para detectar duplicados usando campos específicos
                hash_duplicado = generar_hash_duplicado(
                    fecha, 
                    hora,
                    payment_method,
                    descripcion,
                    money_in,
                    money_out,
                    'WPN'
                )
                
                # Verificar si ya existe en Supabase
                existing = supabase.table('poker_results').select('id').eq('hash_duplicado', hash_duplicado).eq('user_id', str(user_id)).execute()
                
                if existing.data:
                    duplicados_encontrados += 1
                    # Agregar detalle del duplicado
                    duplicados_detalle.append({
                        'fecha': fecha.isoformat(),
                        'hora': hora.isoformat() if hora else None,
                        'tipo_movimiento': tipo_movimiento,
                        'descripcion': descripcion,
                        'importe': importe,
                        'categoria': categoria,
                        'tipo_juego': tipo_juego
                    })
                    continue
                
                # Calcular nivel de buy-in SOLO para registros Buy In
                nivel_buyin = None
                if categoria == 'Torneo' and tipo_movimiento == 'Buy In':
                    nivel_buyin = clasificar_nivel_buyin(importe)
                
                # Crear registro para Supabase
                registro = {
                    'id': str(uuid.uuid4()),
                    'user_id': str(user_id),
                    'fecha': fecha.isoformat(),
                    'hora': hora.isoformat() if hora else None,
                    'tipo_movimiento': tipo_movimiento,
                    'descripcion': descripcion,
                    'importe': importe,
                    'categoria': categoria,
                    'tipo_juego': tipo_juego,
                    'nivel_buyin': nivel_buyin,
                    'sala': 'WPN',
                    'hash_duplicado': hash_duplicado,
                    'created_at': datetime.now().isoformat()
                }
                
                registros_nuevos.append(registro)
                resultados_importados += 1
                
                # Insertar en lotes de 100 registros
                if len(registros_nuevos) >= 100:
                    try:
                        supabase.table('poker_results').insert(registros_nuevos).execute()
                        print(f"Insertados {len(registros_nuevos)} registros en lote. Total importados: {resultados_importados}")
                        registros_nuevos = []
                    except Exception as e:
                        print(f"Error insertando lote: {e}")
                        # Intentar insertar uno por uno si falla el lote
                        for reg in registros_nuevos:
                            try:
                                supabase.table('poker_results').insert(reg).execute()
                                resultados_importados += 1
                            except Exception as e2:
                                print(f"Error insertando registro individual: {e2}")
                        registros_nuevos = []
                
            except Exception as e:
                errores_procesamiento += 1
                print(f"Error procesando fila {index}: {e}")
                continue
        
        # Insertar registros restantes
        if registros_nuevos:
            try:
                supabase.table('poker_results').insert(registros_nuevos).execute()
                print(f"Insertados {len(registros_nuevos)} registros finales. Total importados: {resultados_importados}")
            except Exception as e:
                print(f"Error insertando lote final: {e}")
                # Intentar insertar uno por uno si falla el lote
                for reg in registros_nuevos:
                    try:
                        supabase.table('poker_results').insert(reg).execute()
                        resultados_importados += 1
                    except Exception as e2:
                        print(f"Error insertando registro individual final: {e2}")
        
        print(f"Resumen del procesamiento:")
        print(f"- Registros en archivo: {df_original}")
        print(f"- Eliminados por falta de fecha: {df_sin_fecha}")
        print(f"- Errores de procesamiento: {errores_procesamiento}")
        print(f"- Duplicados omitidos: {duplicados_encontrados}")
        print(f"- Registros importados: {resultados_importados}")
        
        # Procesamiento posterior a la importación
        print("Iniciando procesamiento posterior...")
        niveles_reclasificados = reclasificar_niveles_buyin_automatica(user_id)
        tipos_reclasificados = reclasificar_tipos_juego_automatica(user_id)
        print(f"Niveles de buy-in reclasificados: {niveles_reclasificados}")
        print(f"Tipos de juego reclasificados: {tipos_reclasificados}")
        
        return {
            'mensaje': f'Archivo procesado exitosamente. {resultados_importados} registros importados, {duplicados_encontrados} duplicados omitidos.',
            'resultados_importados': resultados_importados,
            'duplicados_encontrados': duplicados_encontrados,
            'duplicados_detalle': duplicados_detalle
        }
        
    except Exception as e:
        return {'error': f'Error procesando archivo WPN: {str(e)}'}'''

# Buscar y reemplazar la función incorrecta
# Primero encontrar el inicio de la función
start_marker = "def procesar_archivo_wpn_con_progreso(filepath, user_id, progress_callback):"
end_marker = "def procesar_archivo_pokerstars_con_progreso"

# Encontrar las posiciones
start_pos = content.find(start_marker)
if start_pos == -1:
    print("❌ No se encontró la función procesar_archivo_wpn_con_progreso")
    exit(1)

# Buscar el final de la función (próxima función)
end_pos = content.find(end_marker, start_pos)
if end_pos == -1:
    print("❌ No se encontró el final de la función")
    exit(1)

# Extraer la función incorrecta
funcion_incorrecta = content[start_pos:end_pos].rstrip()

# Reemplazar
new_content = content[:start_pos] + funcion_correcta + "\n\n" + content[end_pos:]

# Escribir el archivo
with open('app_working.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("✅ Función procesar_archivo_wpn_con_progreso reemplazada correctamente")
print("✅ Archivo app_working.py actualizado")
