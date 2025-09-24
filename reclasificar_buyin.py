#!/usr/bin/env python3
"""
Rutina para reclasificar registros de Bounty y Winnings basándose en el Buy In correspondiente
"""

import os
from app import app, db, PokerResult, clasificar_nivel_buyin

def reclasificar_niveles_buyin():
    """Reclasifica los niveles de buy-in para registros Bounty y Winnings"""
    with app.app_context():
        print("=== RECLASIFICACIÓN DE NIVELES DE BUY-IN ===\n")
        
        # Obtener todos los registros de torneos con Buy In que ya tienen nivel_buyin
        buyins_clasificados = PokerResult.query.filter(
            PokerResult.categoria == 'Torneo',
            PokerResult.tipo_movimiento == 'Buy In',
            PokerResult.nivel_buyin.isnot(None)
        ).all()
        
        print(f"Registros Buy In clasificados encontrados: {len(buyins_clasificados)}")
        
        # Obtener registros de torneos sin clasificar (todos los tipos de movimiento de torneos)
        registros_sin_clasificar = PokerResult.query.filter(
            PokerResult.categoria == 'Torneo',
            PokerResult.tipo_movimiento.in_(['Bounty', 'Winnings', 'Sit & Crush Jackpot', 'Fee', 'Reentry Fee', 'Reentry Buy In', 'Unregister Buy In', 'Unregister Fee']),
            PokerResult.nivel_buyin.is_(None)
        ).all()
        
        print(f"Registros de torneos sin clasificar: {len(registros_sin_clasificar)}")
        
        if not buyins_clasificados:
            print("❌ No se encontraron registros Buy In clasificados")
            return
        
        if not registros_sin_clasificar:
            print("✅ No hay registros Bounty/Winnings sin clasificar")
            return
        
        # Crear un diccionario de descripción -> nivel_buyin para búsqueda rápida
        descripcion_nivel = {}
        for buyin in buyins_clasificados:
            descripcion_nivel[buyin.descripcion] = buyin.nivel_buyin
        
        print(f"Descripciones de Buy In indexadas: {len(descripcion_nivel)}")
        
        # Reclasificar registros Bounty y Winnings
        reclasificados = 0
        no_encontrados = 0
        errores = 0
        
        for registro in registros_sin_clasificar:
            try:
                nivel_buyin = None
                
                # Método 1: Búsqueda exacta por descripción
                if registro.descripcion in descripcion_nivel:
                    nivel_buyin = descripcion_nivel[registro.descripcion]
                else:
                    # Método 2: Búsqueda por ID del torneo (primeros números)
                    # Extraer ID del torneo (primeros números antes del espacio)
                    partes = registro.descripcion.split(' ', 1)
                    if len(partes) > 1:
                        torneo_id = partes[0]
                        nombre_torneo = partes[1]
                        
                        # Buscar Buy In que comience con el mismo ID
                        for buyin_desc, nivel in descripcion_nivel.items():
                            if buyin_desc.startswith(torneo_id + ' '):
                                nivel_buyin = nivel
                                break
                
                if nivel_buyin:
                    registro.nivel_buyin = nivel_buyin
                    reclasificados += 1
                    print(f"✅ {registro.tipo_movimiento}: {registro.descripcion[:50]}... → {nivel_buyin}")
                else:
                    no_encontrados += 1
                    print(f"❌ No encontrado: {registro.tipo_movimiento}: {registro.descripcion[:50]}...")
            except Exception as e:
                errores += 1
                print(f"⚠️  Error procesando {registro.id}: {e}")
        
        # Guardar cambios
        if reclasificados > 0:
            db.session.commit()
            print(f"\n✅ Cambios guardados en la base de datos")
        
        # Mostrar resumen
        print(f"\n=== RESUMEN ===")
        print(f"Registros reclasificados: {reclasificados}")
        print(f"Registros no encontrados: {no_encontrados}")
        print(f"Errores: {errores}")
        
        # Verificar distribución final
        print(f"\n=== DISTRIBUCIÓN FINAL ===")
        from sqlalchemy import func
        distribucion = db.session.query(
            PokerResult.nivel_buyin, 
            func.count(PokerResult.id)
        ).filter(
            PokerResult.nivel_buyin.isnot(None)
        ).group_by(PokerResult.nivel_buyin).all()
        
        total_clasificados = 0
        for nivel, count in distribucion:
            print(f"{nivel}: {count} registros")
            total_clasificados += count
        
        print(f"Total registros clasificados: {total_clasificados}")
        
        # Mostrar algunos ejemplos de registros reclasificados
        print(f"\n=== EJEMPLOS DE REGISTROS RECLASIFICADOS ===")
        ejemplos = PokerResult.query.filter(
            PokerResult.categoria == 'Torneo',
            PokerResult.tipo_movimiento.in_(['Bounty', 'Winnings']),
            PokerResult.nivel_buyin.isnot(None)
        ).limit(5).all()
        
        for ejemplo in ejemplos:
            print(f"{ejemplo.tipo_movimiento}: {ejemplo.descripcion[:50]}... → {ejemplo.nivel_buyin}")

def analizar_descripciones():
    """Analiza las descripciones para entender los patrones"""
    with app.app_context():
        print("=== ANÁLISIS DE DESCRIPCIONES ===\n")
        
        # Obtener ejemplos de descripciones de Buy In
        buyins = PokerResult.query.filter(
            PokerResult.categoria == 'Torneo',
            PokerResult.tipo_movimiento == 'Buy In'
        ).limit(10).all()
        
        print("Ejemplos de descripciones Buy In:")
        for buyin in buyins:
            print(f"  - {buyin.descripcion}")
        
        # Obtener ejemplos de descripciones de Bounty
        bounties = PokerResult.query.filter(
            PokerResult.categoria == 'Torneo',
            PokerResult.tipo_movimiento == 'Bounty'
        ).limit(5).all()
        
        print(f"\nEjemplos de descripciones Bounty:")
        for bounty in bounties:
            print(f"  - {bounty.descripcion}")
        
        # Obtener ejemplos de descripciones de Winnings
        winnings = PokerResult.query.filter(
            PokerResult.categoria == 'Torneo',
            PokerResult.tipo_movimiento == 'Winnings'
        ).limit(5).all()
        
        print(f"\nEjemplos de descripciones Winnings:")
        for winning in winnings:
            print(f"  - {winning.descripcion}")

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'analizar':
        analizar_descripciones()
    else:
        reclasificar_niveles_buyin()
