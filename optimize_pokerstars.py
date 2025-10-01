#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Script para optimizar la función de Pokerstars (HTML) con inserción masiva

# Leer el archivo
with open('app_working.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Función optimizada para Pokerstars
funcion_pokerstars_optimizada = '''def procesar_archivo_pokerstars_con_progreso(filepath, user_id, progress_callback):
    """Procesa archivos HTML de Pokerstars con inserción masiva optimizada"""
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
        
        # Procesar todos los registros primero
        print("🔄 Procesando registros...")
        for index, fila in enumerate(filas_datos):
            try:
                # Mostrar progreso cada 100 registros
                if (index + 1) % 100 == 0 or (index + 1) == total_registros:
                    porcentaje = ((index + 1) / total_registros) * 100
                    print(f"Progreso: {index + 1}/{total_registros} registros procesados ({porcentaje:.1f}%)")
                    
                    # Enviar progreso al cliente
                    progress_callback(f"data: {json.dumps({'tipo': 'progreso', 'procesados': index + 1, 'total': total_registros, 'porcentaje': porcentaje, 'etapa': 'procesando'})}\\n\\n")
                
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
                
            except Exception as e:
                errores_procesamiento += 1
                print(f"❌ Error procesando fila {index}: {e}")
                continue
        
        print(f"✅ Procesamiento completado. {len(registros_nuevos)} registros preparados")
        
        # Verificar duplicados en lote
        print("🔍 Verificando duplicados...")
        hashes_existentes = set()
        if registros_nuevos:
            # Obtener todos los hashes existentes de una vez
            try:
                existing_hashes = supabase.table('poker_results').select('hash_duplicado').eq('user_id', str(user_id)).execute()
                hashes_existentes = set([record['hash_duplicado'] for record in existing_hashes.data])
                print(f"✅ {len(hashes_existentes)} hashes existentes encontrados")
            except Exception as e:
                print(f"❌ Error obteniendo hashes existentes: {e}")
        
        # Filtrar duplicados
        registros_sin_duplicados = []
        for registro in registros_nuevos:
            if registro['hash_duplicado'] in hashes_existentes:
                duplicados_encontrados += 1
                duplicados_detalle.append({
                    'fecha': registro['fecha'],
                    'hora': registro['hora'],
                    'tipo_movimiento': registro['tipo_movimiento'],
                    'descripcion': registro['descripcion'],
                    'importe': registro['importe'],
                    'categoria': registro['categoria'],
                    'tipo_juego': registro['tipo_juego']
                })
            else:
                registros_sin_duplicados.append(registro)
        
        print(f"✅ {duplicados_encontrados} duplicados encontrados, {len(registros_sin_duplicados)} registros nuevos")
        
        # Insertar registros nuevos en lotes grandes
        if registros_sin_duplicados:
            print("📤 Insertando registros en lotes...")
            batch_size = 200  # Lotes más grandes para mejor rendimiento
            for i in range(0, len(registros_sin_duplicados), batch_size):
                lote = registros_sin_duplicados[i:i+batch_size]
                try:
                    supabase.table('poker_results').insert(lote).execute()
                    resultados_importados += len(lote)
                    print(f"✅ Insertados {len(lote)} registros en lote. Total importados: {resultados_importados}")
                    
                    # Enviar avance del lote al cliente
                    porcentaje_lote = (resultados_importados / len(registros_sin_duplicados)) * 100
                    progress_callback(f"data: {json.dumps({'tipo': 'lote_completado', 'procesados': resultados_importados, 'total': len(registros_sin_duplicados), 'porcentaje': porcentaje_lote, 'lote_size': len(lote), 'etapa': 'insertando'})}\\n\\n")
                    
                except Exception as e:
                    print(f"❌ Error insertando lote: {e}")
                    # Intentar insertar en lotes más pequeños
                    for j in range(0, len(lote), 50):
                        lote_pequeno = lote[j:j+50]
                        try:
                            supabase.table('poker_results').insert(lote_pequeno).execute()
                            resultados_importados += len(lote_pequeno)
                            print(f"✅ Insertados {len(lote_pequeno)} registros en lote pequeño")
                        except Exception as e2:
                            print(f"❌ Error insertando lote pequeño: {e2}")
                            # Como último recurso, insertar uno por uno
                            for reg in lote_pequeno:
                                try:
                                    supabase.table('poker_results').insert(reg).execute()
                                    resultados_importados += 1
                                except Exception as e3:
                                    print(f"❌ Error insertando registro individual: {e3}")
        
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
start_marker = "def procesar_archivo_pokerstars_con_progreso(filepath, user_id, progress_callback):"
end_marker = "def api_importar_progreso"

# Encontrar las posiciones
start_pos = content.find(start_marker)
if start_pos == -1:
    print("❌ No se encontró la función procesar_archivo_pokerstars_con_progreso")
    exit(1)

# Buscar el final de la función (próxima función)
end_pos = content.find(end_marker, start_pos)
if end_pos == -1:
    print("❌ No se encontró el final de la función de Pokerstars")
    exit(1)

# Reemplazar
new_content = content[:start_pos] + funcion_pokerstars_optimizada + "\n\n" + content[end_pos:]

# Escribir el archivo
with open('app_working.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("✅ Función Pokerstars optimizada con inserción masiva")
print("✅ Verificación de duplicados en lote implementada")
print("✅ Inserción en lotes grandes (200 registros)")
print("✅ Archivo app_working.py actualizado")
