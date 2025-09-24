#!/usr/bin/env python3
"""
Script para probar la nueva lógica de categorización
"""

from app import categorizar_movimiento

def test_categorizacion():
    """Prueba la nueva lógica de categorización"""
    print("=== PRUEBAS DE CATEGORIZACIÓN ===\n")
    
    # Casos de prueba
    casos_prueba = [
        # Casos para Money Added, Money Out, Money In -> Cash
        {
            'payment_category': 'Cash',
            'payment_method': 'Money Added',
            'description': 'Cash Game - NLH $1/$2',
            'esperado': ('Cash', 'Money Added', 'NLH')
        },
        {
            'payment_category': 'Cash',
            'payment_method': 'Money Out',
            'description': 'Cash Game - PLO $2/$5',
            'esperado': ('Cash', 'Money Out', 'PLO')
        },
        {
            'payment_category': 'Cash',
            'payment_method': 'Money In',
            'description': 'Cash Game - Stud Hi/Lo $1/$2',
            'esperado': ('Cash', 'Money In', 'Stud Hi/Lo')
        },
        
        # Casos para tipos de juego específicos
        {
            'payment_category': 'Cash',
            'payment_method': 'Winnings',
            'description': 'Cash Game - Stud Hi/Lo $1/$2',
            'esperado': ('Cash', 'Ganancia', 'Stud Hi/Lo')
        },
        {
            'payment_category': 'Cash',
            'payment_method': 'Winnings',
            'description': 'Cash Game - NLO8 $2/$5',
            'esperado': ('Cash', 'Ganancia', 'NLO8')
        },
        {
            'payment_category': 'Cash',
            'payment_method': 'Winnings',
            'description': 'Cash Game - NL Omaha 8 $1/$2',
            'esperado': ('Cash', 'Ganancia', 'NLO8')
        },
        
        # Casos existentes que deben seguir funcionando
        {
            'payment_category': 'Tournament',
            'payment_method': 'Buy In',
            'description': 'Tournament - PLO Hi/Lo $10',
            'esperado': ('Torneo', 'Buy-in', 'PLO Hi/Lo')
        },
        {
            'payment_category': 'Tournament',
            'payment_method': 'Winnings',
            'description': 'Tournament - 5C PLO8 $20',
            'esperado': ('Torneo', 'Ganancia', '5C PLO8')
        }
    ]
    
    # Ejecutar pruebas
    for i, caso in enumerate(casos_prueba, 1):
        print(f"Prueba {i}:")
        print(f"  Payment Category: {caso['payment_category']}")
        print(f"  Payment Method: {caso['payment_method']}")
        print(f"  Description: {caso['description']}")
        
        # Ejecutar categorización
        categoria, tipo_movimiento, tipo_juego = categorizar_movimiento(
            caso['payment_category'],
            caso['payment_method'],
            caso['description']
        )
        
        resultado = (categoria, tipo_movimiento, tipo_juego)
        esperado = caso['esperado']
        
        print(f"  Resultado: {resultado}")
        print(f"  Esperado: {esperado}")
        
        if resultado == esperado:
            print("  ✅ CORRECTO")
        else:
            print("  ❌ INCORRECTO")
        
        print()

if __name__ == '__main__':
    test_categorizacion()
