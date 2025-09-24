#!/usr/bin/env python3
"""
Script para analizar el resultado económico
"""

from app import app, db, PokerResult

def analizar_resultado():
    """Analiza el resultado económico"""
    with app.app_context():
        print('=== ANÁLISIS DE RESULTADO ECONÓMICO ===')
        
        # Obtener todos los registros
        todos_registros = PokerResult.query.all()
        print(f'Total registros: {len(todos_registros)}')
        
        # Calcular resultado económico excluyendo transferencias, retiros y depósitos
        movimientos_poker = [r for r in todos_registros if r.categoria not in ['Transferencia', 'Depósito'] and r.tipo_movimiento not in ['Retiro']]
        resultado_economico = sum(r.importe for r in movimientos_poker)
        
        print(f'Movimientos de poker: {len(movimientos_poker)}')
        print(f'Resultado económico: ${resultado_economico:.2f}')
        
        print()
        print('=== MOVIMIENTOS EXCLUIDOS ===')
        
        # Verificar qué movimientos se excluyen
        transferencias = [r for r in todos_registros if r.categoria == 'Transferencia']
        depositos = [r for r in todos_registros if r.categoria == 'Depósito']
        retiros = [r for r in todos_registros if r.tipo_movimiento == 'Retiro']
        
        print(f'Transferencias: {len(transferencias)} registros')
        if transferencias:
            for r in transferencias[:3]:
                print(f'  - {r.descripcion[:50]}... (${r.importe})')
        
        print(f'Depósitos: {len(depositos)} registros')
        if depositos:
            for r in depositos[:3]:
                print(f'  - {r.descripcion[:50]}... (${r.importe})')
        
        print(f'Retiros: {len(retiros)} registros')
        if retiros:
            for r in retiros[:3]:
                print(f'  - {r.descripcion[:50]}... (${r.importe})')
        
        print()
        print('=== DISTRIBUCIÓN POR CATEGORÍA (MOVIMIENTOS DE POKER) ===')
        categorias = {}
        for r in movimientos_poker:
            cat = r.categoria
            if cat not in categorias:
                categorias[cat] = {'count': 0, 'total': 0}
            categorias[cat]['count'] += 1
            categorias[cat]['total'] += r.importe
        
        for cat, data in categorias.items():
            print(f'{cat}: {data["count"]} registros, ${data["total"]:.2f}')

if __name__ == '__main__':
    analizar_resultado()
