# 🚀 Migración a PostgreSQL - Poker Results API

## 📋 **Resumen de Cambios**

La aplicación ha sido completamente migrada de SQLite a PostgreSQL para soportar el esquema multiusuario completo con UUIDs y funcionalidades avanzadas.

---

## ✅ **Cambios Realizados**

### **1. Configuración de Base de Datos**
- ❌ **Eliminado**: Soporte para SQLite
- ✅ **Agregado**: Solo PostgreSQL con validación de `DATABASE_URL`
- ✅ **Mejorado**: Configuración automática de conexión

### **2. Modelos de Base de Datos**
- ✅ **User**: Actualizado para usar UUIDs como clave primaria
- ✅ **PokerResult**: Actualizado para usar UUIDs y referencias correctas
- ✅ **Tablas**: Nombres explícitos (`users`, `poker_results`)
- ✅ **Campos**: Agregados `created_at`, `last_login`, `is_active`

### **3. Autenticación**
- ✅ **load_user**: Simplificado para solo UUIDs
- ✅ **authenticate_bearer_token**: Optimizado para PostgreSQL
- ✅ **require_auth**: Mejorado para manejo de errores

### **4. Documentación**
- ✅ **ESTRUCTURA_BASE_DATOS_POSTGRESQL.md**: Documentación completa del esquema
- ✅ **setup_postgresql.py**: Script de configuración automática
- ✅ **env.postgresql.example**: Archivo de configuración de ejemplo

---

## 🗄️ **Estructura de Base de Datos**

### **Tabla: `users`**
```sql
CREATE TABLE public.users (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  username character varying(80) NOT NULL UNIQUE,
  email character varying(120) NOT NULL UNIQUE,
  password_hash character varying(120) NOT NULL,
  is_active boolean NOT NULL DEFAULT true,
  is_admin boolean NOT NULL DEFAULT false,
  created_at timestamp with time zone DEFAULT now(),
  last_login timestamp with time zone,
  CONSTRAINT users_pkey PRIMARY KEY (id)
);
```

### **Tabla: `poker_results`**
```sql
CREATE TABLE public.poker_results (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  fecha date NOT NULL,
  hora time without time zone,
  descripcion text NOT NULL,
  importe numeric(10,2) NOT NULL,
  categoria character varying(50) NOT NULL,
  tipo_movimiento character varying(50) NOT NULL,
  tipo_juego character varying(50) NOT NULL,
  sala character varying(50) NOT NULL,
  nivel_buyin character varying(50),
  hash_duplicado character varying(64) NOT NULL,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT poker_results_pkey PRIMARY KEY (id),
  CONSTRAINT poker_results_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id)
);
```

---

## 🔧 **Configuración Requerida**

### **1. Variables de Entorno**
```bash
# Requerido
DATABASE_URL=postgresql://username:password@host:port/database

# Opcional
SECRET_KEY=your-secret-key
FLASK_ENV=development
```

### **2. Instalación de Dependencias**
```bash
pip install psycopg2-binary
# o
pip install psycopg2
```

### **3. Configuración de Base de Datos**
```bash
# Ejecutar script de configuración
python setup_postgresql.py
```

---

## 🚀 **Cómo Usar**

### **1. Configurar Base de Datos**
```bash
# 1. Configurar variable de entorno
export DATABASE_URL="postgresql://user:password@localhost:5432/poker_results"

# 2. Ejecutar script de configuración
python setup_postgresql.py

# 3. Ejecutar aplicación
python app_swagger.py
```

### **2. Acceder a Swagger UI**
```
http://localhost:5001/swagger/
```

### **3. Credenciales de Prueba**
- **Admin**: `admin` / `admin123`
- **Test**: `testuser` / `testpass123`
- **Demo**: `demo` / `demo123`

---

## 📊 **Endpoints Disponibles**

### **🔐 Autenticación**
- `POST /api/auth/login` - Login con token
- `GET /api/auth/token` - Obtener token actual
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
- `GET /api/admin/stats` - Estadísticas generales
- `GET /api/admin/users` - Listar usuarios
- `POST /api/admin/backup` - Crear backup

---

## 🔍 **Ventajas de PostgreSQL**

### **1. Escalabilidad**
- ✅ Soporte para múltiples usuarios concurrentes
- ✅ Índices avanzados para consultas complejas
- ✅ Particionado de tablas para grandes volúmenes

### **2. Seguridad**
- ✅ Row Level Security (RLS)
- ✅ Encriptación de conexiones
- ✅ Auditoría de accesos

### **3. Funcionalidades Avanzadas**
- ✅ UUIDs nativos
- ✅ Funciones de agregación avanzadas
- ✅ Triggers y procedimientos almacenados
- ✅ JSON/JSONB para datos flexibles

### **4. Rendimiento**
- ✅ Optimizador de consultas avanzado
- ✅ Índices parciales y funcionales
- ✅ Consultas paralelas
- ✅ Caché de consultas

---

## ⚠️ **Consideraciones Importantes**

### **1. Migración de Datos**
- Los datos existentes en SQLite necesitan migración
- Usar scripts de migración personalizados
- Validar integridad de datos después de migración

### **2. Configuración de Producción**
- Configurar conexiones pool
- Ajustar parámetros de PostgreSQL
- Implementar backup automático
- Configurar monitoreo

### **3. Seguridad**
- Usar conexiones SSL/TLS
- Implementar RLS para multi-tenancy
- Configurar firewall de base de datos
- Rotar credenciales regularmente

---

## 📚 **Archivos Creados/Modificados**

### **Nuevos Archivos**
- `ESTRUCTURA_BASE_DATOS_POSTGRESQL.md` - Documentación del esquema
- `setup_postgresql.py` - Script de configuración
- `env.postgresql.example` - Archivo de configuración de ejemplo
- `MIGRACION_POSTGRESQL.md` - Esta guía de migración

### **Archivos Modificados**
- `app_swagger.py` - Aplicación principal con soporte PostgreSQL
- `requirements.txt` - Dependencias actualizadas

---

## 🎯 **Próximos Pasos**

1. **Configurar base de datos PostgreSQL**
2. **Ejecutar script de configuración**
3. **Probar endpoints en Swagger UI**
4. **Migrar datos existentes (si los hay)**
5. **Configurar para producción**

---

**📅 Fecha de migración**: 26 de Septiembre de 2025  
**🔧 Versión**: 2.0 (PostgreSQL)  
**👨‍💻 Desarrollado por**: Equipo Poker Results API

