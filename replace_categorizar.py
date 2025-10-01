#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Script para reemplazar la función categorizar_movimiento incorrecta

# Leer el archivo
with open('app_working.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Función correcta
funcion_correcta = '''def categorizar_movimiento(payment_method, descripcion, money_in, money_out):
    """Categorizar movimientos de WPN - VERSIÓN CORRECTA"""
    payment_lower = payment_method.lower() if payment_method else ''
    desc_lower = descripcion.lower() if descripcion else ''
    
    # Mapeo de tipos de movimiento
    tipo_movimiento_map = {
        'buy in': 'Buy In',
        'winnings': 'Winnings',
        'bounty': 'Bounty',
        'fee': 'Fee',
        'reentry fee': 'Reentry Fee',
        'money added': 'Money Added',
        'money out': 'Money Out',
        'money in': 'Money In',
        'payout': 'Payout',
        'reentry buy in': 'Reentry Buy In',
        'unregister buy in': 'Unregister Buy In',
        'unregister fee': 'Unregister Fee',
        'sit & crush jackpot': 'Sit & Crush Jackpot'
    }
    
    tipo_movimiento = tipo_movimiento_map.get(payment_lower, payment_method)
    
    # Determinar categoría
    if 'tournament' in desc_lower or 'bounty' in desc_lower or 'fee' in desc_lower or 'reentry' in desc_lower or 'sit & crush' in desc_lower or 'unregister' in desc_lower or 'on demand' in desc_lower:
        categoria = 'Torneo'
    elif 'money added' in payment_lower or 'money out' in payment_lower or 'money in' in payment_lower:
        categoria = 'Cash'
    elif 'transfer' in payment_lower:
        categoria = 'Transferencia'
    elif 'withdrawal' in payment_lower:
        categoria = 'Retiro'
    elif 'deposit' in payment_lower:
        categoria = 'Depósito'
    else:
        categoria = 'Otro'
    
    # Regla especial para Payout
    if tipo_movimiento == 'Payout':
        categoria = 'Retiro'
    
    # Determinar tipo de juego
    if categoria == 'Torneo':
        if 'sit & go' in desc_lower:
            tipo_juego = 'Sit & Go'
        elif 'plo' in desc_lower or 'omaha' in desc_lower:
            if 'hi/lo' in desc_lower or 'hi lo' in desc_lower:
                if '5c' in desc_lower or '5 card' in desc_lower:
                    tipo_juego = '5C PLO8'
                elif '8' in desc_lower:
                    tipo_juego = 'PLO8'
                else:
                    tipo_juego = 'PLO Hi/Lo'
            elif '8' in desc_lower:
                tipo_juego = 'PLO8'
            else:
                tipo_juego = 'PLO'
        elif 'stud' in desc_lower:
            if 'hi/lo' in desc_lower or 'hi lo' in desc_lower:
                tipo_juego = 'Stud Hi/Lo'
            else:
                tipo_juego = 'Stud'
        elif 'nlh' in desc_lower or 'holdem' in desc_lower or 'nl hold' in desc_lower:
            tipo_juego = 'NLH'
        elif 'nlo8' in desc_lower:
            tipo_juego = 'NLO8'
        else:
            tipo_juego = 'Torneo'
    elif categoria == 'Cash':
        if 'stud' in desc_lower and ('hi/lo' in desc_lower or 'hi lo' in desc_lower):
            tipo_juego = 'Stud Hi/Lo'
        elif 'nlo8' in desc_lower:
            tipo_juego = 'NLO8'
        else:
            tipo_juego = 'Cash'
    else:
        tipo_juego = 'Otro'
    
    return categoria, tipo_movimiento, tipo_juego'''

# Función incorrecta a reemplazar
funcion_incorrecta = '''def categorizar_movimiento(payment_category, payment_method, description):
    """Categoriza automáticamente los movimientos de WPN"""
    descripcion_lower = description.lower()
    payment_method_lower = payment_method.lower()
    
    # Categoría principal
    if 'tournament' in descripcion_lower or 'tourney' in descripcion_lower:
        categoria = 'Torneo'
    elif 'cash' in descripcion_lower or 'ring' in descripcion_lower:
        categoria = 'Cash'
    elif 'sit' in descripcion_lower and 'go' in descripcion_lower:
        categoria = 'Sit & Go'
    else:
        categoria = 'Otro'
    
    # Tipo de juego
    if 'nl' in descripcion_lower or 'no limit' in descripcion_lower:
        tipo_juego = 'No Limit Hold\\'em'
    elif 'pl' in descripcion_lower or 'pot limit' in descripcion_lower:
        tipo_juego = 'Pot Limit Omaha'
    elif 'limit' in descripcion_lower:
        tipo_juego = 'Limit Hold\\'em'
    elif 'omaha' in descripcion_lower:
        tipo_juego = 'Omaha'
    else:
        tipo_juego = 'Hold\\'em'
    
    return categoria, payment_method, tipo_juego'''

# Reemplazar
if funcion_incorrecta in content:
    content = content.replace(funcion_incorrecta, funcion_correcta)
    print("✅ Función reemplazada correctamente")
else:
    print("❌ No se encontró la función incorrecta")

# Escribir el archivo
with open('app_working.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Archivo app_working.py actualizado")
