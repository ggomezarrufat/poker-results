#!/bin/bash

# Script para detener la aplicación Poker Results

echo "🛑 Deteniendo aplicación Poker Results..."

# Buscar procesos de Python que ejecuten la aplicación
PIDS=$(ps aux | grep "app_multiusuario_working.py" | grep -v grep | awk '{print $2}')

if [ -z "$PIDS" ]; then
    echo "ℹ️  No se encontraron procesos de la aplicación ejecutándose"
else
    echo "🔍 Procesos encontrados: $PIDS"
    
    # Terminar procesos de manera suave
    for PID in $PIDS; do
        echo "📤 Enviando señal TERM al proceso $PID..."
        kill -TERM $PID 2>/dev/null
    done
    
    # Esperar un momento
    sleep 2
    
    # Verificar si aún están ejecutándose y forzar terminación si es necesario
    REMAINING=$(ps aux | grep "app_multiusuario_working.py" | grep -v grep | awk '{print $2}')
    if [ ! -z "$REMAINING" ]; then
        echo "⚠️  Algunos procesos aún están ejecutándose, forzando terminación..."
        for PID in $REMAINING; do
            echo "💀 Enviando señal KILL al proceso $PID..."
            kill -KILL $PID 2>/dev/null
        done
    fi
    
    echo "✅ Aplicación detenida"
fi

# También buscar procesos en el puerto 5001
PORT_PID=$(lsof -ti:5001 2>/dev/null)
if [ ! -z "$PORT_PID" ]; then
    echo "🔍 Proceso en puerto 5001: $PORT_PID"
    echo "📤 Terminando proceso en puerto 5001..."
    kill -TERM $PORT_PID 2>/dev/null
    sleep 1
    # Si aún está ejecutándose, forzar terminación
    if lsof -ti:5001 >/dev/null 2>&1; then
        kill -KILL $PORT_PID 2>/dev/null
    fi
    echo "✅ Puerto 5001 liberado"
fi

echo "🏁 Script de parada completado"

