# 📚 Endpoints Completos de la API Poker Results con Swagger

## 🎯 **Resumen de Implementación**

✅ **Todos los endpoints han sido agregados a Swagger con documentación completa**
✅ **Autenticación Bearer implementada y funcionando**
✅ **Documentación automática generada en `/swagger/`**

---

## 🔐 **Autenticación**

### **Login para Obtener Token**
- **POST** `/api/auth/login`
- **Descripción**: Iniciar sesión y obtener token de autenticación
- **Body**: `{"username": "testuser", "password": "testpass123"}`
- **Respuesta**: `{"mensaje": "Login exitoso", "token": "...", "user_id": 1, "username": "testuser"}`

### **Obtener Token Actual**
- **GET** `/api/auth/token`
- **Descripción**: Obtener token de autenticación actual
- **Headers**: `Authorization: Bearer TOKEN`
- **Respuesta**: `{"token": "...", "user_id": 1, "username": "testuser"}`

### **Logout**
- **POST** `/api/auth/logout`
- **Descripción**: Cerrar sesión
- **Headers**: `Authorization: Bearer TOKEN`
- **Respuesta**: `{"mensaje": "Logout exitoso"}`

---

## 📊 **Informes (Reports)**

### **Resultados Filtrados**
- **GET** `/api/reports/results`
- **Descripción**: Obtener resultados filtrados con estadísticas y gráfico de últimos 10 días
- **Headers**: `Authorization: Bearer TOKEN`
- **Parámetros**:
  - `categoria` (string): Filtrar por categoría
  - `tipo_juego` (string): Filtrar por tipo de juego
  - `nivel_buyin` (string): Filtrar por nivel de buy-in
  - `sala` (string): Filtrar por sala
  - `fecha_inicio` (string): Fecha de inicio (YYYY-MM-DD)
  - `fecha_fin` (string): Fecha de fin (YYYY-MM-DD)
  - `page` (int): Número de página (default: 1)
  - `per_page` (int): Registros por página (default: 50)
- **Respuesta**: Incluye resultados, estadísticas y gráfico de últimos 10 días

### **Opciones de Filtros**
- **GET** `/api/reports/options`
- **Descripción**: Obtener opciones disponibles para filtros
- **Headers**: `Authorization: Bearer TOKEN`
- **Respuesta**: `{"categorias": [...], "tipos_juego": [...], "niveles_buyin": [...], "salas": [...]}`

---

## 📈 **Análisis (Analysis)**

### **Análisis Completo**
- **GET** `/api/analysis/insights`
- **Descripción**: Análisis avanzado con insights para gestión del juego
- **Headers**: `Authorization: Bearer TOKEN`
- **Respuesta**: Análisis completo con recomendaciones

### **Análisis por Buy-in**
- **GET** `/api/analysis/buyin`
- **Descripción**: Análisis de rendimiento por nivel de buy-in
- **Headers**: `Authorization: Bearer TOKEN`
- **Respuesta**: Estadísticas detalladas por nivel de buy-in

### **Análisis por Sala**
- **GET** `/api/analysis/sala`
- **Descripción**: Análisis de rendimiento por sala
- **Headers**: `Authorization: Bearer TOKEN`
- **Respuesta**: Estadísticas detalladas por sala

### **Análisis Temporal**
- **GET** `/api/analysis/temporal`
- **Descripción**: Análisis de patrones temporales
- **Headers**: `Authorization: Bearer TOKEN`
- **Respuesta**: Patrones por día de la semana, hora, etc.

### **Análisis por Tipo de Juego**
- **GET** `/api/analysis/juego`
- **Descripción**: Análisis de rendimiento por tipo de juego
- **Headers**: `Authorization: Bearer TOKEN`
- **Respuesta**: Estadísticas por Hold'em, Omaha, etc.

### **Análisis de Consistencia**
- **GET** `/api/analysis/consistencia`
- **Descripción**: Análisis de consistencia del jugador
- **Headers**: `Authorization: Bearer TOKEN`
- **Respuesta**: Métricas de consistencia y variabilidad

---

## 📁 **Importación (Import)**

### **Subir Archivo**
- **POST** `/api/import/upload`
- **Descripción**: Importar archivo de resultados de poker
- **Headers**: `Authorization: Bearer TOKEN`
- **Body**: `multipart/form-data` con archivo Excel
- **Respuesta**: `{"mensaje": "Importación exitosa", "resultados_importados": N, "duplicados_encontrados": N}`

### **Listar Archivos**
- **GET** `/api/import/files`
- **Descripción**: Listar archivos importados por el usuario
- **Headers**: `Authorization: Bearer TOKEN`
- **Respuesta**: `{"archivos": [{"nombre": "...", "tamaño": N, "fecha_modificacion": "..."}]}`

### **Estado de Importación**
- **GET** `/api/import/status`
- **Descripción**: Obtener estado de la última importación
- **Headers**: `Authorization: Bearer TOKEN`
- **Respuesta**: `{"total_registros": N, "ultima_importacion": "...", "usuario": "..."}`

---

## ⚙️ **Administración (Admin)**

### **Salas Disponibles**
- **GET** `/api/admin/available-rooms`
- **Descripción**: Obtener las salas disponibles del usuario actual
- **Headers**: `Authorization: Bearer TOKEN`
- **Respuesta**: `{"salas": [{"sala": "...", "registros": N}]}`

### **Eliminar Todos los Registros**
- **POST** `/api/admin/delete-all`
- **Descripción**: Eliminar todos los registros del usuario actual
- **Headers**: `Authorization: Bearer TOKEN`
- **Respuesta**: `{"mensaje": "Todos los registros eliminados", "registros_eliminados": N}`

### **Eliminar por Sala**
- **POST** `/api/admin/delete-by-room`
- **Descripción**: Eliminar registros de una sala específica
- **Headers**: `Authorization: Bearer TOKEN`
- **Body**: `{"sala": "PokerStars"}`
- **Respuesta**: `{"mensaje": "Registros eliminados", "sala": "...", "registros_eliminados": N}`

### **Estadísticas Generales**
- **GET** `/api/admin/stats`
- **Descripción**: Obtener estadísticas generales del usuario
- **Headers**: `Authorization: Bearer TOKEN`
- **Respuesta**: Estadísticas completas por sala, categoría, fechas, etc.

### **Listar Usuarios** (Solo Admin)
- **GET** `/api/admin/users`
- **Descripción**: Obtener lista de todos los usuarios (solo admin)
- **Headers**: `Authorization: Bearer TOKEN`
- **Respuesta**: `{"usuarios": [{"id": N, "username": "...", "email": "...", "is_admin": bool, "total_registros": N}]}`

### **Crear Backup**
- **POST** `/api/admin/backup`
- **Descripción**: Crear backup de los datos del usuario
- **Headers**: `Authorization: Bearer TOKEN`
- **Respuesta**: `{"mensaje": "Backup creado exitosamente", "archivo": "...", "total_registros": N}`

---

## 🧪 **Ejemplos de Uso**

### **1. Login y Obtener Token**
```bash
curl -X POST http://localhost:5001/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username": "testuser", "password": "testpass123"}'
```

### **2. Obtener Resultados con Filtros**
```bash
curl -H 'Authorization: Bearer TOKEN_AQUI' \
     "http://localhost:5001/api/reports/results?categoria=Torneo&sala=PokerStars&page=1&per_page=10"
```

### **3. Análisis Completo**
```bash
curl -H 'Authorization: Bearer TOKEN_AQUI' \
     http://localhost:5001/api/analysis/insights
```

### **4. Subir Archivo**
```bash
curl -X POST -H 'Authorization: Bearer TOKEN_AQUI' \
     -F 'archivo=@mi_archivo.xlsx' \
     http://localhost:5001/api/import/upload
```

### **5. Estadísticas de Administración**
```bash
curl -H 'Authorization: Bearer TOKEN_AQUI' \
     http://localhost:5001/api/admin/stats
```

---

## 📋 **Modelos de Datos Documentados**

### **PokerResult**
- `fecha`: Fecha del movimiento
- `hora`: Hora del movimiento
- `tipo_movimiento`: Tipo (Buy In, Cash Out, etc.)
- `descripcion`: Descripción del movimiento
- `importe`: Importe (positivo o negativo)
- `categoria`: Categoría (Torneo, Cash, etc.)
- `tipo_juego`: Tipo de juego (Hold'em, Omaha, etc.)
- `nivel_buyin`: Nivel de buy-in
- `sala`: Sala de poker

### **User**
- `id`: ID del usuario
- `username`: Nombre de usuario
- `email`: Email del usuario
- `is_admin`: Si es administrador
- `password_hash`: Hash de la contraseña

### **Estadísticas**
- `cantidad_torneos`: Número total de torneos
- `total_registros`: Número total de registros
- `suma_importes`: Suma total de importes
- `total_invertido`: Total invertido
- `total_ganancias`: Total ganado
- `roi`: Retorno de inversión
- `resultado_economico`: Resultado económico neto

---

## 🔧 **Configuración de Swagger**

### **URL de Swagger UI**
```
http://localhost:5001/swagger/
```

### **URL de Especificación OpenAPI**
```
http://localhost:5001/swagger.json
```

### **Características de Swagger**
- ✅ **Documentación automática** de todos los endpoints
- ✅ **Modelos de datos** completamente documentados
- ✅ **Ejemplos de request/response** incluidos
- ✅ **Interfaz interactiva** para probar endpoints
- ✅ **Autenticación Bearer** integrada
- ✅ **Validación de parámetros** automática
- ✅ **Códigos de error** documentados

---

## ⚠️ **Notas Importantes**

### **🔒 Seguridad**
- Todos los endpoints (excepto login) requieren autenticación
- El token Bearer se genera en el login y debe incluirse en cada request
- Los tokens son válidos durante la sesión del servidor

### **📊 Base de Datos**
- La aplicación usa SQLite para desarrollo local
- Para producción, configurar `DATABASE_URL` para PostgreSQL/Supabase
- El esquema multiusuario requiere la columna `user_id` en `poker_result`

### **🚀 Despliegue**
- La aplicación está lista para desplegar en Vercel
- Configurar variables de entorno para producción
- Usar un servidor WSGI para producción (no el servidor de desarrollo)

---

## 🎉 **¡Implementación Completa!**

**✅ 20+ endpoints documentados y funcionando**
**✅ Autenticación Bearer implementada**
**✅ Documentación Swagger completa**
**✅ Interfaz interactiva disponible**
**✅ Listo para integración con Allin**

**🔗 Accede a Swagger UI**: `http://localhost:5001/swagger/`

