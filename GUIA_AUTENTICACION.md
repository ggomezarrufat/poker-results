# 🔐 Guía de Autenticación - Poker Results API

## ✅ **Token de Autenticación Obtenido Exitosamente**

### **🎯 Credenciales de Prueba Creadas:**
- **Usuario**: `testuser`
- **Contraseña**: `testpass123`
- **Token actual**: `JCGyBUvZJP1HikXVUSv4Ku-EvXRy6wsF6xqG6O69xDc`

---

## **📋 Métodos para Obtener Token**

### **Método 1: Script Automático (Recomendado)**

```bash
cd /Users/gga/Proyectos/poker-results
source venv/bin/activate
python get_token.py
```

**Entrada:**
```
👤 Usuario: testuser
🔒 Contraseña: testpass123
```

**Salida:**
```
✅ Login exitoso!
👤 Usuario: testuser
🆔 User ID: 1
🔑 Token: JCGyBUvZJP1HikXVUSv4Ku-EvXRy6wsF6xqG6O69xDc
```

### **Método 2: API Directa**

```bash
curl -X POST http://localhost:5001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "testpass123"}'
```

**Respuesta:**
```json
{
  "mensaje": "Login exitoso",
  "token": "JCGyBUvZJP1HikXVUSv4Ku-EvXRy6wsF6xqG6O69xDc",
  "user_id": 1,
  "username": "testuser"
}
```

### **Método 3: Interfaz Web + Swagger**

1. **Acceder a la web**: http://localhost:5001/login
2. **Iniciar sesión** con `testuser` / `testpass123`
3. **Ir a Swagger**: http://localhost:5001/swagger/
4. **El token se maneja automáticamente** a través de cookies

---

## **🔧 Cómo Usar el Token**

### **En Swagger UI:**

1. **Abrir Swagger**: http://localhost:5001/swagger/
2. **Hacer clic en "Authorize"** (🔒) en la parte superior
3. **En el campo "Value"** pegar: `JCGyBUvZJP1HikXVUSv4Ku-EvXRy6wsF6xqG6O69xDc`
4. **Hacer clic en "Authorize"**
5. **Cerrar el modal**
6. **Ahora todos los endpoints están autenticados**

### **Con curl:**

```bash
# Ejemplo: Obtener opciones de filtros
curl -H "Authorization: Bearer JCGyBUvZJP1HikXVUSv4Ku-EvXRy6wsF6xqG6O69xDc" \
     http://localhost:5001/api/reports/options

# Ejemplo: Obtener resultados
curl -H "Authorization: Bearer JCGyBUvZJP1HikXVUSv4Ku-EvXRy6wsF6xqG6O69xDc" \
     "http://localhost:5001/api/reports/results?fecha_inicio=2025-01-01"
```

### **Con Python requests:**

```python
import requests

headers = {
    "Authorization": "Bearer JCGyBUvZJP1HikXVUSv4Ku-EvXRy6wsF6xqG6O69xDc"
}

# Obtener opciones
response = requests.get("http://localhost:5001/api/reports/options", headers=headers)
print(response.json())

# Obtener resultados
response = requests.get("http://localhost:5001/api/reports/results", headers=headers)
print(response.json())
```

---

## **📊 Endpoints Disponibles con Autenticación**

### **🔐 Autenticación (Auth)**
- `POST /api/auth/login` - Iniciar sesión y obtener token
- `GET /api/auth/token` - Obtener token actual
- `POST /api/auth/logout` - Cerrar sesión

### **📁 Importación (Import)**
- `POST /api/import/upload` - Subir archivos de resultados

### **📊 Informes (Reports)**
- `GET /api/reports/results` - Resultados filtrados + gráfico últimos 10 días
- `GET /api/reports/options` - Opciones para filtros

### **📈 Análisis (Analysis)**
- `GET /api/analysis/insights` - Análisis avanzado con insights

### **⚙️ Administración (Admin)**
- `POST /api/admin/delete-all` - Eliminar todos los registros
- `POST /api/admin/delete-by-room` - Eliminar por sala
- `GET /api/admin/available-rooms` - Salas disponibles

---

## **🧪 Probar Endpoints**

### **1. Obtener Opciones de Filtros:**
```bash
curl -H "Authorization: Bearer JCGyBUvZJP1HikXVUSv4Ku-EvXRy6wsF6xqG6O69xDc" \
     http://localhost:5001/api/reports/options
```

### **2. Obtener Resultados (con gráfico últimos 10 días):**
```bash
curl -H "Authorization: Bearer JCGyBUvZJP1HikXVUSv4Ku-EvXRy6wsF6xqG6O69xDc" \
     http://localhost:5001/api/reports/results
```

### **3. Obtener Análisis Avanzado:**
```bash
curl -H "Authorization: Bearer JCGyBUvZJP1HikXVUSv4Ku-EvXRy6wsF6xqG6O69xDc" \
     http://localhost:5001/api/analysis/insights
```

---

## **⚠️ Notas Importantes**

### **🔒 Seguridad:**
- **El token expira** cuando se cierra la sesión
- **Cada login genera un nuevo token**
- **El token es específico por sesión**

### **🔄 Renovar Token:**
```bash
# Si el token expira, obtener uno nuevo
python get_token.py
```

### **📝 Logs de la Aplicación:**
- Los logs muestran las peticiones autenticadas
- Busca líneas como: `"GET /api/reports/results HTTP/1.1" 200`

---

## **🎉 ¡Listo para Usar!**

Ahora puedes:

1. **✅ Usar Swagger UI** con autenticación completa
2. **✅ Probar todos los endpoints** de la API
3. **✅ Ver el gráfico de últimos 10 días** funcionando
4. **✅ Usar la API desde cualquier cliente** con el token

**🔗 Acceder a Swagger**: http://localhost:5001/swagger/
**🔑 Token actual**: `JCGyBUvZJP1HikXVUSv4Ku-EvXRy6wsF6xqG6O69xDc`

