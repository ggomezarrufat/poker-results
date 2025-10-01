# Guía de Swagger en app_working.py

## 🎯 **Swagger Integrado Exitosamente**

La aplicación `app_working.py` ahora incluye **Swagger UI** como funcionalidad adicional, manteniendo toda la funcionalidad existente.

## 🚀 **Cómo Acceder a Swagger**

### **1. Iniciar la Aplicación**
```bash
cd /Users/gga/Proyectos/poker-results
source venv/bin/activate
python app_working.py
```

### **2. Acceder a Swagger UI**
- **URL**: `http://localhost:5001/swagger/`
- **Puerto**: 5001 (mismo que la aplicación principal)

## 📋 **Endpoints Disponibles en Swagger**

### **🔐 Autenticación (`/api/auth`)**
- **POST** `/api/auth/login` - Iniciar sesión de usuario
  - **Body**: `{"username": "usuario", "password": "contraseña"}`
  - **Respuesta**: Token de autenticación y datos del usuario

### **📊 Reportes (`/api/reports`)**
- **GET** `/api/reports/opciones` - Obtener opciones de filtros
  - **Autenticación**: Requerida
  - **Respuesta**: Categorías, tipos de juego, niveles de buy-in, salas

- **GET** `/api/reports/resultados` - Obtener resultados filtrados
  - **Autenticación**: Requerida
  - **Parámetros**: `categoria`, `sala`, `page`, `per_page`
  - **Respuesta**: Resultados paginados y estadísticas

### **👨‍💼 Administración (`/api/admin`)**
- **GET** `/api/admin/estadisticas` - Obtener estadísticas del usuario
  - **Autenticación**: Requerida
  - **Respuesta**: Estadísticas generales y por sala

## 🔧 **Características Técnicas**

### **Configuración de Swagger**
- **Framework**: Flask-RESTX
- **Documentación**: OpenAPI 3.0
- **UI**: Swagger UI integrada
- **Prefijo API**: `/api`
- **Documentación**: `/swagger/`

### **Namespaces Organizados**
- `auth` - Autenticación de usuarios
- `reports` - Informes y reportes
- `analysis` - Análisis avanzado
- `import` - Importación de datos
- `admin` - Administración

### **Modelos de Datos Documentados**
- `LoginRequest` - Datos de login
- `LoginResponse` - Respuesta de login
- `PokerResult` - Resultado de poker
- `Stats` - Estadísticas
- `Opciones` - Opciones de filtros
- `Error` - Mensajes de error
- `Success` - Mensajes de éxito

## 🎮 **Cómo Usar Swagger UI**

### **1. Acceder a la Interfaz**
1. Abre `http://localhost:5001/swagger/` en tu navegador
2. Verás la documentación completa de la API

### **2. Probar Endpoints**
1. **Expandir** el endpoint que quieres probar
2. **Hacer clic** en "Try it out"
3. **Completar** los parámetros requeridos
4. **Ejecutar** con "Execute"

### **3. Autenticación**
- Para endpoints que requieren autenticación, primero usa `/api/auth/login`
- La autenticación se maneja automáticamente por la sesión web

## 🔄 **Compatibilidad**

### **Funcionalidad Existente**
- ✅ **Todas las rutas web** siguen funcionando normalmente
- ✅ **Todas las funcionalidades** de la aplicación principal se mantienen
- ✅ **Base de datos** Supabase sigue siendo la misma
- ✅ **Autenticación** web sigue funcionando

### **Nuevas Funcionalidades**
- ✅ **API REST** documentada con Swagger
- ✅ **Endpoints** organizados por funcionalidad
- ✅ **Documentación** automática y interactiva
- ✅ **Pruebas** de API desde el navegador

## 📝 **Ejemplos de Uso**

### **Ejemplo 1: Obtener Opciones de Filtros**
```bash
curl -X GET "http://localhost:5001/api/reports/opciones" \
  -H "Cookie: session=tu_sesion_aqui"
```

### **Ejemplo 2: Obtener Resultados Filtrados**
```bash
curl -X GET "http://localhost:5001/api/reports/resultados?categoria=Torneo&page=1&per_page=10" \
  -H "Cookie: session=tu_sesion_aqui"
```

### **Ejemplo 3: Obtener Estadísticas**
```bash
curl -X GET "http://localhost:5001/api/admin/estadisticas" \
  -H "Cookie: session=tu_sesion_aqui"
```

## 🛠️ **Desarrollo y Mantenimiento**

### **Agregar Nuevos Endpoints**
1. **Crear** la clase Resource en el namespace apropiado
2. **Agregar** decoradores `@api.doc`, `@api.expect`, `@api.response`
3. **Documentar** parámetros y respuestas
4. **Probar** en Swagger UI

### **Modificar Modelos**
1. **Actualizar** los modelos en la sección "MODELOS DE SWAGGER"
2. **Referenciar** en los endpoints correspondientes
3. **Verificar** que la documentación se actualice automáticamente

## 🎉 **¡Swagger Integrado Exitosamente!**

Ahora tienes:
- ✅ **Aplicación web** completa funcionando
- ✅ **API REST** documentada con Swagger
- ✅ **Interfaz interactiva** para probar endpoints
- ✅ **Documentación automática** de la API
- ✅ **Compatibilidad total** con funcionalidad existente

**¡Disfruta explorando tu API con Swagger UI!** 🚀

