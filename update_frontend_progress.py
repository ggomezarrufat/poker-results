#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Script para actualizar el frontend con avance de lotes

# Leer el archivo
with open('templates/importar.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Función actualizada
funcion_actualizada = '''function actualizarProgreso(data) {
    console.log('Datos recibidos:', data);
    const progressBar = document.querySelector('.progress-bar');
    const progresoTexto = document.getElementById('progreso-texto');
    
    if (data.tipo === 'inicio') {
        progresoTexto.innerHTML = `<small class="text-muted">Total de registros encontrados: ${data.total_registros}. Iniciando procesamiento...</small>`;
    } else if (data.tipo === 'progreso') {
        const porcentaje = Math.round(data.porcentaje);
        progressBar.style.width = porcentaje + '%';
        progressBar.setAttribute('aria-valuenow', porcentaje);
        progresoTexto.innerHTML = `<small class="text-muted">Procesando: ${data.procesados}/${data.total} registros (${porcentaje}%)</small>`;
    } else if (data.tipo === 'lote_completado') {
        const porcentaje = Math.round(data.porcentaje);
        progressBar.style.width = porcentaje + '%';
        progressBar.setAttribute('aria-valuenow', porcentaje);
        progresoTexto.innerHTML = `<small class="text-success"><i class="fas fa-check-circle me-1"></i>Lote completado: ${data.procesados}/${data.total} registros importados (${porcentaje}%) - Lote de ${data.lote_size} registros</small>`;
    } else if (data.tipo === 'completado') {
        mostrarResultado(data);
    } else if (data.error) {
        mostrarError(data.error);
    } else {
        // Si no hay tipo específico, asumir que es el resultado final
        console.log('Resultado sin tipo específico:', data);
        mostrarResultado(data);
    }
}'''

# Buscar y reemplazar la función
start_marker = "function actualizarProgreso(data) {"
end_marker = "// Función para mostrar el resultado final"

# Encontrar las posiciones
start_pos = content.find(start_marker)
if start_pos == -1:
    print("❌ No se encontró la función actualizarProgreso")
    exit(1)

# Buscar el final de la función
end_pos = content.find(end_marker, start_pos)
if end_pos == -1:
    print("❌ No se encontró el final de la función actualizarProgreso")
    exit(1)

# Reemplazar
new_content = content[:start_pos] + funcion_actualizada + "\n\n" + content[end_pos:]

# Escribir el archivo
with open('templates/importar.html', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("✅ Función actualizarProgreso actualizada")
print("✅ Avance de lotes agregado al frontend")
print("✅ Archivo templates/importar.html actualizado")
