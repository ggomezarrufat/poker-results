# 🎯 Guía para Usar Swagger UI - Poker Results API

## 🔗 **Acceso a Swagger UI**

**URL**: `http://localhost:5001/swagger/`

---

## 🔐 **Cómo Hacer Login en Swagger UI**

### **Paso 1: Ir al Endpoint de Login**
1. Abre `http://localhost:5001/swagger/`
2. Busca la sección **"Authentication"**
3. Haz clic en **"POST /api/auth/login"**

### **Paso 2: Configurar la Petición**
1. Haz clic en **"Try it out"**
2. En el campo **"Request body"**, ingresa:
```json
{
  "username": "testuser",
  "password": "testpass123"
}
```

### **Paso 3: Ejecutar la Petición**
1. Haz clic en **"Execute"**
2. Deberías ver una respuesta **200** con:
```json
{
  "mensaje": "Login exitoso",
  "token": "rjIMOEAkmAtpSHnDpbDjGXsoKK7aW5vtD3sEYdQNyGk",
  "user_id": 1,
  "username": "testuser"
}
```

### **Paso 4: Copiar el Token**
1. Copia el valor del campo **"token"** de la respuesta
2. Este token lo usarás para autenticarte en otros endpoints

---

## 🔑 **Cómo Usar la Autenticación en Swagger UI**

### **Método 1: Botón "Authorize" (Recomendado)**
1. En la parte superior de Swagger UI, busca el botón **"Authorize"** 🔒
2. Haz clic en **"Authorize"**
3. En el campo **"Value"**, ingresa: `Bearer TU_TOKEN_AQUI`
   - Ejemplo: `Bearer rjIMOEAkmAtpSHnDpbDjGXsoKK7aW5vtD3sEYdQNyGk`
4. Haz clic en **"Authorize"**
5. Haz clic en **"Close"**

### **Método 2: Manual en cada Endpoint**
1. En cualquier endpoint que requiera autenticación
2. Busca el campo **"Authorization"**
3. Ingresa: `Bearer TU_TOKEN_AQUI`

---

## 📊 **Endpoints Principales para Probar**

### **1. Informes - Resultados**
- **Endpoint**: `GET /api/reports/results`
- **Descripción**: Obtener resultados filtrados
- **Parámetros opcionales**:
  - `categoria`: "Torneo"
  - `sala`: "PokerStars"
  - `page`: 1
  - `per_page`: 10

### **2. Informes - Opciones**
- **Endpoint**: `GET /api/reports/options`
- **Descripción**: Obtener opciones para filtros
- **No requiere parámetros**

### **3. Análisis - Insights**
- **Endpoint**: `GET /api/analysis/insights`
- **Descripción**: Análisis completo
- **No requiere parámetros**

### **4. Administración - Estadísticas**
- **Endpoint**: `GET /api/admin/stats`
- **Descripción**: Estadísticas generales
- **No requiere parámetros**

---

## 🧪 **Ejemplo Completo de Uso**

### **Paso 1: Login**
```json
POST /api/auth/login
{
  "username": "testuser",
  "password": "testpass123"
}
```

**Respuesta**:
```json
{
  "mensaje": "Login exitoso",
  "token": "rjIMOEAkmAtpSHnDpbDjGXsoKK7aW5vtD3sEYdQNyGk",
  "user_id": 1,
  "username": "testuser"
}
```

### **Paso 2: Autorizar**
1. Clic en **"Authorize"** 🔒
2. Ingresar: `Bearer rjIMOEAkmAtpSHnDpbDjGXsoKK7aW5vtD3sEYdQNyGk`
3. Clic en **"Authorize"** y **"Close"**

### **Paso 3: Probar Endpoint**
1. Ir a `GET /api/reports/options`
2. Clic en **"Try it out"**
3. Clic en **"Execute"**
4. Ver la respuesta con las opciones disponibles

---

## ⚠️ **Solución al Error 415**

Si ves el error **"415 Unsupported Media Type"**:

### **Problema**:
- Swagger UI está enviando credenciales como parámetros de URL
- El servidor espera un cuerpo JSON

### **Solución**:
1. **Asegúrate de usar el campo "Request body"** en lugar de parámetros
2. **Ingresa el JSON correcto**:
```json
{
  "username": "testuser",
  "password": "testpass123"
}
```
3. **No uses parámetros de consulta** en la URL

---

## 🔧 **Comandos curl para Referencia**

### **Login**:
```bash
curl -X POST http://localhost:5001/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username": "testuser", "password": "testpass123"}'
```

### **Usar Token**:
```bash
curl -H 'Authorization: Bearer TOKEN_AQUI' \
     http://localhost:5001/api/reports/options
```

---

## 📋 **Lista de Endpoints Disponibles**

### **🔐 Autenticación**
- `POST /api/auth/login` - Login
- `GET /api/auth/token` - Obtener token
- `POST /api/auth/logout` - Logout

### **📊 Informes**
- `GET /api/reports/results` - Resultados filtrados
- `GET /api/reports/options` - Opciones de filtros

### **📈 Análisis**
- `GET /api/analysis/insights` - Análisis completo
- `GET /api/analysis/buyin` - Análisis por buy-in
- `GET /api/analysis/sala` - Análisis por sala
- `GET /api/analysis/temporal` - Análisis temporal
- `GET /api/analysis/juego` - Análisis por juego
- `GET /api/analysis/consistencia` - Análisis de consistencia

### **📁 Importación**
- `POST /api/import/upload` - Subir archivo
- `GET /api/import/files` - Listar archivos
- `GET /api/import/status` - Estado de importación

### **⚙️ Administración**
- `GET /api/admin/available-rooms` - Salas disponibles
- `POST /api/admin/delete-all` - Eliminar todos
- `POST /api/admin/delete-by-room` - Eliminar por sala
- `GET /api/admin/stats` - Estadísticas
- `GET /api/admin/users` - Listar usuarios
- `POST /api/admin/backup` - Crear backup

---

## 🎉 **¡Listo para Usar!**

Con esta guía puedes:
- ✅ Hacer login correctamente en Swagger UI
- ✅ Usar la autenticación Bearer
- ✅ Probar todos los endpoints
- ✅ Evitar el error 415
- ✅ Integrar con Allin usando los tokens

**🔗 Accede ahora**: `http://localhost:5001/swagger/`

