# 📚 Poker Results API - Documentación Swagger

## ✅ **Swagger Implementado Exitosamente**

Se ha implementado **Swagger/OpenAPI** completo para la API de Poker Results utilizando Flask-RESTX.

### **🚀 Acceso a Swagger UI**

Una vez que la aplicación esté ejecutándose:

```bash
# Ejecutar la aplicación con Swagger
cd /Users/gga/Proyectos/poker-results
source venv/bin/activate
python app_swagger.py
```

**URLs de acceso:**
- **Swagger UI Interactiva**: http://localhost:5001/swagger/
- **Especificación JSON**: http://localhost:5001/swagger.json
- **Aplicación Principal**: http://localhost:5001/

### **📋 Endpoints Documentados**

#### **🔐 Autenticación (Auth)**
- Manejo de usuarios y sesiones a través de la interfaz web

#### **📁 Importación (Import)**
- `POST /api/import/upload` - Subir archivos de resultados (WPN/PokerStars)

#### **📊 Informes (Reports)**
- `GET /api/reports/results` - Obtener resultados filtrados y estadísticas
- `GET /api/reports/options` - Obtener opciones para filtros

#### **📈 Análisis (Analysis)**
- `GET /api/analysis/insights` - Análisis avanzado con insights

#### **⚙️ Administración (Admin)**
- `POST /api/admin/delete-all` - Eliminar todos los registros del usuario
- `POST /api/admin/delete-by-room` - Eliminar registros por sala
- `GET /api/admin/available-rooms` - Obtener salas disponibles

### **🎯 Características de Swagger**

#### **📖 Documentación Completa**
- **Descripciones detalladas** de cada endpoint
- **Parámetros de entrada** con tipos y validaciones
- **Modelos de respuesta** estructurados
- **Códigos de estado** y mensajes de error

#### **🧪 Interfaz Interactiva**
- **Probar endpoints** directamente desde el navegador
- **Autenticación** integrada (Bearer tokens)
- **Ejemplos de requests/responses**
- **Validación en tiempo real**

#### **📚 Modelos de Datos**

##### **PokerResult Model**
```json
{
  "id": 1,
  "fecha": "2025-09-25",
  "hora": "14:30:00",
  "tipo_movimiento": "Buy In",
  "descripcion": "Tournament #123",
  "importe": -11.00,
  "categoria": "Torneo",
  "tipo_juego": "Hold'em",
  "nivel_buyin": "Micro ($1-$10)",
  "sala": "PokerStars"
}
```

##### **Estadísticas Model**
```json
{
  "cantidad_torneos": 150,
  "total_registros": 300,
  "suma_importes": 450.75,
  "total_invertido": 1650.00,
  "total_ganancias": 2100.75,
  "roi": 27.3,
  "resultado_economico": 450.75
}
```

##### **ResultadoDiario Model**
```json
{
  "fecha": "2025-09-25",
  "resultado": 25.50,
  "movimientos": 3
}
```

### **🔧 Funcionalidades Especiales**

#### **📅 Gráfico de Últimos 10 Días**
El endpoint `/api/reports/results` incluye `resultados_diarios` que:
- ✅ **Siempre muestra los últimos 10 días** desde la fecha actual
- ✅ **Independiente de filtros** aplicados a otros datos
- ✅ **Incluye días sin datos** como cero
- ✅ **Filtrado por usuario** (multiusuario)

#### **🔒 Seguridad Multiusuario**
- **Todos los endpoints** filtran automáticamente por `user_id`
- **Autenticación requerida** en todos los endpoints API
- **Aislamiento de datos** entre usuarios

#### **📈 Análisis Avanzado**
- **Rendimiento por buy-in**: ROI, rachas, salas
- **Rendimiento por sala**: Victorias, tipos de juego
- **Patrones temporales**: Días de semana, horas
- **Análisis de consistencia**: Variabilidad, rachas
- **Recomendaciones automáticas**: Basadas en datos

### **🎨 Interfaz Swagger**

#### **Características Visuales:**
- **Organización por namespaces**: Auth, Import, Reports, Analysis, Admin
- **Colores por método HTTP**: GET (azul), POST (verde), DELETE (rojo)
- **Expandible/Colapsable**: Navegación fácil
- **Try it out**: Pruebas en vivo
- **Documentación inline**: Descripciones y ejemplos

#### **Parámetros de Filtros:**
```
GET /api/reports/results
- fecha_inicio: 2025-09-01
- fecha_fin: 2025-09-30
- tipo_movimiento: "Buy In"
- monto_minimo: 10.0
- categorias[]: ["Torneo", "Cash"]
- tipos_juego[]: ["Hold'em", "Omaha"]
- niveles_buyin[]: ["Micro ($1-$10)"]
- salas[]: ["PokerStars", "WPN"]
```

### **🔄 Migración desde app_multiusuario.py**

Para cambiar a la versión con Swagger:

```bash
# Cambiar archivo principal
mv app_multiusuario.py app_multiusuario_backup.py
mv app_swagger.py app_multiusuario.py

# O usar directamente
python app_swagger.py
```

### **💡 Uso Recomendado**

1. **Desarrollo**: Usar Swagger UI para probar endpoints
2. **Documentación**: Compartir URL de Swagger con el equipo
3. **Integración**: Usar especificación JSON para generar clientes
4. **Depuración**: Verificar requests/responses en tiempo real

### **🎯 Beneficios**

- ✅ **Documentación automática** y actualizada
- ✅ **Pruebas interactivas** sin herramientas externas
- ✅ **Estándares OpenAPI** para integración
- ✅ **Validación automática** de datos
- ✅ **Interfaz profesional** para desarrolladores
- ✅ **Especificación exportable** para otros servicios

La implementación de Swagger convierte la API en una herramienta profesional, fácil de usar y mantener, perfecta para desarrollo y producción.

