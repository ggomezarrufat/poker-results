#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Script para optimizar ambas funciones de importación para Supabase

# Leer el archivo
with open('app_working.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Función optimizada de Pokerstars
funcion_pokerstars_optimizada = '''def procesar_archivo_pokerstars_con_progreso(filepath, user_id, progress_callback):
    """Procesa archivos HTML de Pokerstars con callback de progreso para SSE - VERSIÓN OPTIMIZADA PARA SUPABASE"""
    try:
        # Leer archivo HTML
        with open(filepath, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Buscar tabla de transacciones con múltiples selectores
        tabla = None
        selectores = [
            'table[data-testid="transactions-table"]',
            'table.transactions',
            'table.dataTable',
            'table[class*="transaction"]',
            'table[class*="history"]',
            'table'
        ]
        
        for selector in selectores:
            tabla = soup.select_one(selector)
            if tabla:
                print(f"✅ Tabla encontrada con selector: {selector}")
                break
        
        if not tabla:
            return {'error': 'No se encontró tabla de transacciones en el archivo HTML'}
        
        # Obtener filas de la tabla
        filas = tabla.find_all('tr')
        print(f"Total filas encontradas: {len(filas)}")
        
        # Filtrar filas que contengan datos (no headers)
        filas_datos = []
        for fila in filas:
            celdas = fila.find_all(['td', 'th'])
            if len(celdas) >= 3:  # Mínimo 3 columnas
                # Verificar si es header (contiene texto como "Date", "Description", etc.)
                texto_celdas = [celda.get_text(strip=True).lower() for celda in celdas]
                if not any(palabra in ' '.join(texto_celdas) for palabra in ['date', 'description', 'amount', 'type', 'fecha', 'descripción', 'importe', 'tipo']):
                    filas_datos.append(fila)
        
        total_registros = len(filas_datos)
        print(f"Total registros a procesar: {total_registros}")
        
        if total_registros == 0:
            return {'error': 'No se encontraron registros válidos en la tabla'}
        
        # Enviar total de registros al cliente
        progress_callback(f"data: {json.dumps({'tipo': 'inicio', 'total_registros': total_registros})}\\n\\n")
        
        resultados_importados = 0
        duplicados_encontrados = 0
        errores_procesamiento = 0
        duplicados_detalle = []
        registros_nuevos = []
        
        for index, fila in enumerate(filas_datos):
            try:
                # Mostrar progreso cada 50 registros
                if (index + 1) % 50 == 0 or (index + 1) == total_registros:
                    porcentaje = ((index + 1) / total_registros) * 100
                    print(f"Progreso: {index + 1}/{total_registros} registros procesados ({porcentaje:.1f}%)")
                    
                    # Enviar progreso al cliente
                    progress_callback(f"data: {json.dumps({'tipo': 'progreso', 'procesados': index + 1, 'total': total_registros, 'porcentaje': porcentaje})}\\n\\n")
                
                celdas = fila.find_all(['td', 'th'])
                if len(celdas) < 3:
                    continue
                
                # Extraer datos de las celdas
                fecha_str = celdas[0].get_text(strip=True)
                descripcion = celdas[1].get_text(strip=True)
                importe_str = celdas[2].get_text(strip=True)
                tipo_str = celdas[3].get_text(strip=True) if len(celdas) > 3 else ''
                
                # Procesar fecha
                try:
                    fecha = pd.to_datetime(fecha_str).date()
                except:
                    continue
                
                # Procesar importe
                try:
                    # Limpiar símbolos de moneda y espacios
                    importe_limpio = importe_str.replace('$', '').replace(',', '').replace('€', '').replace('£', '').strip()
                    importe = float(importe_limpio)
                    
                    # Limitar importe a un rango seguro para evitar overflow numérico en Supabase
                    if abs(importe) > 999999.99:
                        importe = 999999.99 if importe > 0 else -999999.99
                        print(f"⚠️  Importe limitado: {importe} (original: {importe_limpio})")
                except:
                    continue
                
                # Categorizar movimiento
                categoria, tipo_movimiento, tipo_juego = categorizar_movimiento_pokerstars(tipo_str, descripcion, '')
                
                # Generar hash para detección de duplicados
                hash_duplicado = generar_hash_duplicado(
                    fecha, None, tipo_str, descripcion, importe, importe, 'Pokerstars'
                )
                
                # Verificar duplicados
                duplicado_existente = supabase.table('poker_results').select('id').eq('hash_duplicado', hash_duplicado).eq('user_id', str(user_id)).execute()
                
                if duplicado_existente.data:
                    duplicados_encontrados += 1
                    duplicados_detalle.append({
                        'fecha': str(fecha),
                        'hora': None,
                        'tipo_movimiento': tipo_movimiento,
                        'descripcion': descripcion,
                        'importe': importe,
                        'categoria': categoria,
                        'tipo_juego': tipo_juego
                    })
                    continue
                
                # Clasificar nivel de buy-in
                nivel_buyin = clasificar_nivel_buyin(importe) if categoria == 'Torneo' else None
                
                # Crear registro
                registro = {
                    'id': str(uuid.uuid4()),
                    'user_id': str(user_id),
                    'fecha': fecha.isoformat(),
                    'hora': None,
                    'descripcion': descripcion,
                    'importe': round(importe, 2),  # Redondear a 2 decimales
                    'categoria': categoria,
                    'tipo_movimiento': tipo_movimiento,
                    'tipo_juego': tipo_juego,
                    'nivel_buyin': nivel_buyin,
                    'sala': 'Pokerstars',
                    'hash_duplicado': hash_duplicado
                }
                
                registros_nuevos.append(registro)
                resultados_importados += 1
                
                # Insertar en lotes de 50 registros (optimizado para Supabase)
                if len(registros_nuevos) >= 50:
                    try:
                        supabase.table('poker_results').insert(registros_nuevos).execute()
                        print(f"✅ Insertados {len(registros_nuevos)} registros en lote. Total importados: {resultados_importados}")
                        
                        # Enviar avance del lote al cliente
                        porcentaje_lote = (resultados_importados / total_registros) * 100
                        progress_callback(f"data: {json.dumps({'tipo': 'lote_completado', 'procesados': resultados_importados, 'total': total_registros, 'porcentaje': porcentaje_lote, 'lote_size': len(registros_nuevos)})}\\n\\n")
                        
                        registros_nuevos = []
                    except Exception as e:
                        print(f"❌ Error insertando lote: {e}")
                        # Intentar insertar en lotes más pequeños
                        for i in range(0, len(registros_nuevos), 10):
                            lote_pequeno = registros_nuevos[i:i+10]
                            try:
                                supabase.table('poker_results').insert(lote_pequeno).execute()
                                print(f"✅ Insertados {len(lote_pequeno)} registros en lote pequeño")
                            except Exception as e2:
                                print(f"❌ Error insertando lote pequeño: {e2}")
                                # Como último recurso, insertar uno por uno
                                for reg in lote_pequeno:
                                    try:
                                        supabase.table('poker_results').insert(reg).execute()
                                    except Exception as e3:
                                        print(f"❌ Error insertando registro individual: {e3}")
                        registros_nuevos = []
                
            except Exception as e:
                errores_procesamiento += 1
                print(f"❌ Error procesando fila {index}: {e}")
                continue
        
        # Insertar registros restantes
        if registros_nuevos:
            try:
                supabase.table('poker_results').insert(registros_nuevos).execute()
                print(f"✅ Insertados {len(registros_nuevos)} registros finales. Total importados: {resultados_importados}")
                
                # Enviar avance final del lote al cliente
                porcentaje_final = (resultados_importados / total_registros) * 100
                progress_callback(f"data: {json.dumps({'tipo': 'lote_completado', 'procesados': resultados_importados, 'total': total_registros, 'porcentaje': porcentaje_final, 'lote_size': len(registros_nuevos)})}\\n\\n")
                
            except Exception as e:
                print(f"❌ Error insertando lote final: {e}")
                # Intentar insertar en lotes más pequeños
                for i in range(0, len(registros_nuevos), 10):
                    lote_pequeno = registros_nuevos[i:i+10]
                    try:
                        supabase.table('poker_results').insert(lote_pequeno).execute()
                        print(f"✅ Insertados {len(lote_pequeno)} registros finales en lote pequeño")
                    except Exception as e2:
                        print(f"❌ Error insertando lote pequeño final: {e2}")
                        # Como último recurso, insertar uno por uno
                        for reg in lote_pequeno:
                            try:
                                supabase.table('poker_results').insert(reg).execute()
                            except Exception as e3:
                                print(f"❌ Error insertando registro individual final: {e3}")
        
        print(f"📊 Resumen del procesamiento:")
        print(f"- Registros en archivo: {total_registros}")
        print(f"- Errores de procesamiento: {errores_procesamiento}")
        print(f"- Duplicados omitidos: {duplicados_encontrados}")
        print(f"- Registros importados: {resultados_importados}")
        
        # Procesamiento posterior a la importación
        print("🔄 Iniciando procesamiento posterior...")
        niveles_reclasificados = reclasificar_niveles_buyin_automatica(user_id)
        tipos_reclasificados = reclasificar_tipos_juego_automatica(user_id)
        print(f"✅ Niveles de buy-in reclasificados: {niveles_reclasificados}")
        print(f"✅ Tipos de juego reclasificados: {tipos_reclasificados}")
        
        return {
            'mensaje': f'Archivo procesado exitosamente. {resultados_importados} registros importados, {duplicados_encontrados} duplicados omitidos.',
            'resultados_importados': resultados_importados,
            'duplicados_encontrados': duplicados_encontrados,
            'duplicados_detalle': duplicados_detalle
        }
        
    except Exception as e:
        return {'error': f'Error procesando archivo Pokerstars: {str(e)}'}'''

# Buscar y reemplazar la función de Pokerstars
start_marker_pokerstars = "def procesar_archivo_pokerstars_con_progreso(filepath, user_id, progress_callback):"
end_marker_pokerstars = "def api_importar_progreso"

# Encontrar las posiciones
start_pos_pokerstars = content.find(start_marker_pokerstars)
if start_pos_pokerstars == -1:
    print("❌ No se encontró la función procesar_archivo_pokerstars_con_progreso")
    exit(1)

# Buscar el final de la función (próxima función)
end_pos_pokerstars = content.find(end_marker_pokerstars, start_pos_pokerstars)
if end_pos_pokerstars == -1:
    print("❌ No se encontró el final de la función de Pokerstars")
    exit(1)

# Reemplazar función de Pokerstars
new_content = content[:start_pos_pokerstars] + funcion_pokerstars_optimizada + "\n\n" + content[end_pos_pokerstars:]

# Ahora actualizar la función de WPN para incluir avance de lotes
funcion_wpn_actualizada = '''def procesar_archivo_wpn_con_progreso(filepath, user_id, progress_callback):
    """Procesa archivos Excel de WPN con callback de progreso para SSE - VERSIÓN OPTIMIZADA PARA SUPABASE"""
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
                
                # Determinar importe (Money In - Money Out) con límite para evitar overflow
                importe = money_in - money_out
                # Limitar importe a un rango seguro para evitar overflow numérico en Supabase
                if abs(importe) > 999999.99:
                    importe = 999999.99 if importe > 0 else -999999.99
                    print(f"⚠️  Importe limitado: {importe} (original: {money_in - money_out})")
                
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
                    'importe': round(importe, 2),  # Redondear a 2 decimales
                    'categoria': categoria,
                    'tipo_juego': tipo_juego,
                    'nivel_buyin': nivel_buyin,
                    'sala': 'WPN',
                    'hash_duplicado': hash_duplicado
                    # Remover created_at para que Supabase lo maneje automáticamente
                }
                
                registros_nuevos.append(registro)
                resultados_importados += 1
                
                # Insertar en lotes de 50 registros (optimizado para Supabase)
                if len(registros_nuevos) >= 50:
                    try:
                        supabase.table('poker_results').insert(registros_nuevos).execute()
                        print(f"✅ Insertados {len(registros_nuevos)} registros en lote. Total importados: {resultados_importados}")
                        
                        # Enviar avance del lote al cliente
                        porcentaje_lote = (resultados_importados / total_registros) * 100
                        progress_callback(f"data: {json.dumps({'tipo': 'lote_completado', 'procesados': resultados_importados, 'total': total_registros, 'porcentaje': porcentaje_lote, 'lote_size': len(registros_nuevos)})}\\n\\n")
                        
                        registros_nuevos = []
                    except Exception as e:
                        print(f"❌ Error insertando lote: {e}")
                        # Intentar insertar en lotes más pequeños
                        for i in range(0, len(registros_nuevos), 10):
                            lote_pequeno = registros_nuevos[i:i+10]
                            try:
                                supabase.table('poker_results').insert(lote_pequeno).execute()
                                print(f"✅ Insertados {len(lote_pequeno)} registros en lote pequeño")
                            except Exception as e2:
                                print(f"❌ Error insertando lote pequeño: {e2}")
                                # Como último recurso, insertar uno por uno
                                for reg in lote_pequeno:
                                    try:
                                        supabase.table('poker_results').insert(reg).execute()
                                    except Exception as e3:
                                        print(f"❌ Error insertando registro individual: {e3}")
                        registros_nuevos = []
                
            except Exception as e:
                errores_procesamiento += 1
                print(f"❌ Error procesando fila {index}: {e}")
                continue
        
        # Insertar registros restantes
        if registros_nuevos:
            try:
                supabase.table('poker_results').insert(registros_nuevos).execute()
                print(f"✅ Insertados {len(registros_nuevos)} registros finales. Total importados: {resultados_importados}")
                
                # Enviar avance final del lote al cliente
                porcentaje_final = (resultados_importados / total_registros) * 100
                progress_callback(f"data: {json.dumps({'tipo': 'lote_completado', 'procesados': resultados_importados, 'total': total_registros, 'porcentaje': porcentaje_final, 'lote_size': len(registros_nuevos)})}\\n\\n")
                
            except Exception as e:
                print(f"❌ Error insertando lote final: {e}")
                # Intentar insertar en lotes más pequeños
                for i in range(0, len(registros_nuevos), 10):
                    lote_pequeno = registros_nuevos[i:i+10]
                    try:
                        supabase.table('poker_results').insert(lote_pequeno).execute()
                        print(f"✅ Insertados {len(lote_pequeno)} registros finales en lote pequeño")
                    except Exception as e2:
                        print(f"❌ Error insertando lote pequeño final: {e2}")
                        # Como último recurso, insertar uno por uno
                        for reg in lote_pequeno:
                            try:
                                supabase.table('poker_results').insert(reg).execute()
                            except Exception as e3:
                                print(f"❌ Error insertando registro individual final: {e3}")
        
        print(f"📊 Resumen del procesamiento:")
        print(f"- Registros en archivo: {df_original}")
        print(f"- Eliminados por falta de fecha: {df_sin_fecha}")
        print(f"- Errores de procesamiento: {errores_procesamiento}")
        print(f"- Duplicados omitidos: {duplicados_encontrados}")
        print(f"- Registros importados: {resultados_importados}")
        
        # Procesamiento posterior a la importación
        print("🔄 Iniciando procesamiento posterior...")
        niveles_reclasificados = reclasificar_niveles_buyin_automatica(user_id)
        tipos_reclasificados = reclasificar_tipos_juego_automatica(user_id)
        print(f"✅ Niveles de buy-in reclasificados: {niveles_reclasificados}")
        print(f"✅ Tipos de juego reclasificados: {tipos_reclasificados}")
        
        return {
            'mensaje': f'Archivo procesado exitosamente. {resultados_importados} registros importados, {duplicados_encontrados} duplicados omitidos.',
            'resultados_importados': resultados_importados,
            'duplicados_encontrados': duplicados_encontrados,
            'duplicados_detalle': duplicados_detalle
        }
        
    except Exception as e:
        return {'error': f'Error procesando archivo WPN: {str(e)}'}'''

# Buscar y reemplazar la función de WPN
start_marker_wpn = "def procesar_archivo_wpn_con_progreso(filepath, user_id, progress_callback):"
end_marker_wpn = "def procesar_archivo_pokerstars_con_progreso"

# Encontrar las posiciones
start_pos_wpn = new_content.find(start_marker_wpn)
if start_pos_wpn == -1:
    print("❌ No se encontró la función procesar_archivo_wpn_con_progreso")
    exit(1)

# Buscar el final de la función (próxima función)
end_pos_wpn = new_content.find(end_marker_wpn, start_pos_wpn)
if end_pos_wpn == -1:
    print("❌ No se encontró el final de la función de WPN")
    exit(1)

# Reemplazar función de WPN
final_content = new_content[:start_pos_wpn] + funcion_wpn_actualizada + "\n\n" + new_content[end_pos_wpn:]

# Escribir el archivo
with open('app_working.py', 'w', encoding='utf-8') as f:
    f.write(final_content)

print("✅ Ambas funciones optimizadas para Supabase")
print("✅ Avance de lotes agregado")
print("✅ Archivo app_working.py actualizado")
