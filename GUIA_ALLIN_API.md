# 🔗 Guía para Usar la API desde Allin

## ✅ **Endpoint de Login Funcionando**

Tu API ya tiene un endpoint de login completamente funcional que puedes usar desde Allin.

---

## **🔐 Endpoint de Login**

### **URL:**
```
POST http://localhost:5001/api/auth/login
```

### **Headers:**
```
Content-Type: application/json
```

### **Body (JSON):**
```json
{
  "username": "testuser",
  "password": "testpass123"
}
```

### **Respuesta Exitosa (200):**
```json
{
  "mensaje": "Login exitoso",
  "token": "djPclK0eUz0ct39fpWX8h0lcKQt-rXFOUOSLsuXeK5A",
  "user_id": 1,
  "username": "testuser"
}
```

### **Respuesta de Error (401):**
```json
{
  "error": "Credenciales inválidas"
}
```

---

## **📋 Implementación en Allin**

### **1. Paso 1: Login para Obtener Token**

```javascript
// En Allin, crear una función de login
async function loginToPokerAPI() {
    const loginUrl = 'http://localhost:5001/api/auth/login';
    
    const credentials = {
        username: 'testuser',
        password: 'testpass123'
    };
    
    try {
        const response = await fetch(loginUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(credentials)
        });
        
        if (response.ok) {
            const data = await response.json();
            console.log('Login exitoso:', data);
            return data.token; // Guardar el token
        } else {
            console.error('Error en login:', response.status);
            return null;
        }
    } catch (error) {
        console.error('Error de conexión:', error);
        return null;
    }
}
```

### **2. Paso 2: Usar Token en Requests**

```javascript
// Función para hacer requests autenticados
async function makeAuthenticatedRequest(endpoint, token) {
    const baseUrl = 'http://localhost:5001';
    const url = `${baseUrl}${endpoint}`;
    
    try {
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            return data;
        } else {
            console.error('Error en request:', response.status);
            return null;
        }
    } catch (error) {
        console.error('Error de conexión:', error);
        return null;
    }
}
```

### **3. Paso 3: Ejemplo de Uso Completo**

```javascript
// Ejemplo completo de uso
async function getPokerResults() {
    // 1. Hacer login
    const token = await loginToPokerAPI();
    
    if (!token) {
        console.error('No se pudo obtener token');
        return;
    }
    
    // 2. Usar el token para obtener datos
    const results = await makeAuthenticatedRequest('/api/reports/results', token);
    const options = await makeAuthenticatedRequest('/api/reports/options', token);
    
    if (results) {
        console.log('Resultados obtenidos:', results);
        console.log('Gráfico últimos 10 días:', results.resultados_diarios);
    }
    
    if (options) {
        console.log('Opciones disponibles:', options);
    }
}

// Ejecutar
getPokerResults();
```

---

## **🔧 Endpoints Disponibles para Allin**

### **📊 Informes (Reports)**
- `GET /api/reports/results` - Resultados filtrados + gráfico últimos 10 días
- `GET /api/reports/options` - Opciones para filtros

### **📈 Análisis (Analysis)**
- `GET /api/analysis/insights` - Análisis avanzado

### **📁 Importación (Import)**
- `POST /api/import/upload` - Subir archivos

### **⚙️ Administración (Admin)**
- `GET /api/admin/available-rooms` - Salas disponibles
- `POST /api/admin/delete-all` - Eliminar todos los registros
- `POST /api/admin/delete-by-room` - Eliminar por sala

---

## **🧪 Comandos curl para Pruebas**

### **1. Login:**
```bash
curl -X POST http://localhost:5001/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username": "testuser", "password": "testpass123"}'
```

### **2. Obtener Resultados (con token):**
```bash
curl -H 'Authorization: Bearer djPclK0eUz0ct39fpWX8h0lcKQt-rXFOUOSLsuXeK5A' \
     http://localhost:5001/api/reports/results
```

### **3. Obtener Opciones:**
```bash
curl -H 'Authorization: Bearer djPclK0eUz0ct39fpWX8h0lcKQt-rXFOUOSLsuXeK5A' \
     http://localhost:5001/api/reports/options
```

### **4. Análisis Avanzado:**
```bash
curl -H 'Authorization: Bearer djPclK0eUz0ct39fpWX8h0lcKQt-rXFOUOSLsuXeK5A' \
     http://localhost:5001/api/analysis/insights
```

---

## **📊 Estructura de Respuestas**

### **Resultados (`/api/reports/results`):**
```json
{
  "resultados": [
    {
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
  ],
  "estadisticas": {
    "cantidad_torneos": 150,
    "total_registros": 300,
    "suma_importes": 450.75,
    "total_invertido": 1650.00,
    "total_ganancias": 2100.75,
    "roi": 27.3,
    "resultado_economico": 450.75
  },
  "resultados_diarios": [
    {
      "fecha": "2025-09-25",
      "resultado": 25.50,
      "movimientos": 3
    }
  ]
}
```

### **Opciones (`/api/reports/options`):**
```json
{
  "categorias": ["Torneo", "Cash", "Transferencia"],
  "tipos_juego": ["Hold'em", "Omaha", "Stud"],
  "niveles_buyin": ["Micro ($1-$10)", "Low ($11-$50)"],
  "salas": ["PokerStars", "WPN", "GGPoker"]
}
```

---

## **⚠️ Notas Importantes**

### **🔒 Seguridad:**
- **El token expira** cuando se cierra la sesión
- **Cada login genera un nuevo token**
- **Siempre incluir el token** en el header `Authorization: Bearer TOKEN`

### **🔄 Manejo de Errores:**
- **401 Unauthorized**: Token inválido o expirado → Hacer login nuevamente
- **403 Forbidden**: Sin permisos para el endpoint
- **404 Not Found**: Endpoint no existe
- **500 Internal Server Error**: Error del servidor

### **📝 Logs:**
- Los logs de la aplicación muestran todas las peticiones
- Busca líneas como: `"POST /api/auth/login HTTP/1.1" 200`

---

## **🎉 ¡Listo para Usar!**

Tu API está completamente funcional y lista para ser integrada con Allin:

1. **✅ Endpoint de login** funcionando
2. **✅ Autenticación Bearer** implementada
3. **✅ Todos los endpoints** documentados
4. **✅ Gráfico de últimos 10 días** incluido
5. **✅ Manejo de errores** robusto

**🔗 URL Base**: `http://localhost:5001`
**🔑 Token actual**: `djPclK0eUz0ct39fpWX8h0lcKQt-rXFOUOSLsuXeK5A`

