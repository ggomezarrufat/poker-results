# Analizador de Resultados de Poker

Una aplicación web en Python para analizar resultados de poker de diferentes salas.

## Características

- **Importación de archivos Excel**: Soporte para archivos de WPN y Pokerstars
- **Base de datos local**: SQLite para almacenar todos los datos
- **Control de duplicados**: Sistema inteligente para evitar registros duplicados
- **Informes detallados**: Análisis económico, estadísticas de torneos y ROI
- **Filtros avanzados**: Por fechas, montos, tipos de movimiento

## Instalación

1. Instalar dependencias:
```bash
pip install -r requirements.txt
```

2. Ejecutar la aplicación:
```bash
python app.py
```

3. Abrir en el navegador: http://localhost:5000

## Uso

### Importar Resultados
1. Ve a la sección "Importar"
2. Selecciona la sala (WPN o Pokerstars)
3. Sube tu archivo Excel
4. Los datos se procesarán y almacenarán en la base de datos

### Generar Informes
1. Ve a la sección "Informes"
2. Aplica filtros según necesites
3. Visualiza estadísticas y resultados detallados

## Estructura de Datos

Los datos importados incluyen:
- Fecha
- Tipo de movimiento
- Descripción
- Importe (puede ser negativo)
- Categoría
- Tipo de juego
- Sala de origen

## Próximos Pasos

- Implementar lógica específica para procesar archivos de WPN
- Implementar lógica específica para procesar archivos de Pokerstars
- Agregar más tipos de informes y gráficos
- Soporte para más salas de poker
