#!/usr/bin/env python3
"""
Script para verificar el contenido del archivo index.html directamente
"""

def check_file():
    """Verificar el contenido del archivo index.html"""
    file_path = '/Users/gga/Proyectos/poker-results/templates/index.html'
    
    print("🔍 Verificando archivo index.html directamente...")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"✅ Archivo leído correctamente ({len(content)} caracteres)")
        
        if "Características Principales" in content:
            print("❌ ERROR: 'Características Principales' encontrada en el archivo")
            print("📋 Contexto:")
            import re
            pattern = r'.{0,200}Características Principales.{0,200}'
            match = re.search(pattern, content, re.DOTALL)
            if match:
                print(match.group(0))
        else:
            print("✅ 'Características Principales' NO encontrada en el archivo")
        
        if "Base de Datos Local" in content:
            print("❌ ERROR: 'Base de Datos Local' encontrada en el archivo")
        else:
            print("✅ 'Base de Datos Local' NO encontrada en el archivo")
        
        if "Zona de Peligro" in content:
            print("✅ 'Zona de Peligro' encontrada correctamente")
        else:
            print("❌ ERROR: 'Zona de Peligro' NO encontrada")
        
        # Buscar la línea donde debería estar "Zona de Peligro"
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            if "Zona de Peligro" in line:
                print(f"📍 'Zona de Peligro' encontrada en la línea {i}")
                break
        
        # Buscar si hay alguna referencia a características
        caracteristicas_lines = [i for i, line in enumerate(lines, 1) if "Características" in line]
        if caracteristicas_lines:
            print(f"❌ ERROR: Referencias a 'Características' encontradas en líneas: {caracteristicas_lines}")
        else:
            print("✅ No hay referencias a 'Características' en el archivo")
            
    except Exception as e:
        print(f"❌ Error leyendo archivo: {e}")

if __name__ == "__main__":
    check_file()

