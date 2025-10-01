# 🗄️ Estructura de Base de Datos PostgreSQL - Poker Results API

## 📋 **Resumen**

Esta aplicación utiliza PostgreSQL como base de datos principal con soporte completo para múltiples usuarios. La estructura está optimizada para el análisis de resultados de poker con funcionalidades de autenticación, autorización y análisis avanzado.

---

## 🏗️ **Esquema de Base de Datos**

### **Tabla: `users`**
Almacena información de usuarios del sistema.

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

**Campos:**
- `id` (uuid, PK): Identificador único del usuario
- `username` (varchar): Nombre de usuario único
- `email` (varchar): Email único del usuario
- `password_hash` (varchar): Hash de la contraseña (pbkdf2:sha256)
- `is_active` (boolean): Estado activo del usuario
- `is_admin` (boolean): Permisos de administrador
- `created_at` (timestamp): Fecha de creación
- `last_login` (timestamp): Último acceso

---

### **Tabla: `poker_results`**
Almacena todos los resultados de poker de los usuarios.

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

**Campos:**
- `id` (uuid, PK): Identificador único del resultado
- `user_id` (uuid, FK): Referencia al usuario propietario
- `fecha` (date): Fecha del movimiento
- `hora` (time): Hora del movimiento
- `descripcion` (text): Descripción detallada del movimiento
- `importe` (numeric): Importe monetario (positivo/negativo)
- `categoria` (varchar): Categoría del movimiento (Torneo, Cash, etc.)
- `tipo_movimiento` (varchar): Tipo de movimiento (Buy In, Cash Out, etc.)
- `tipo_juego` (varchar): Tipo de juego (Hold'em, Omaha, etc.)
- `sala` (varchar): Sala de poker (PokerStars, WPN, etc.)
- `nivel_buyin` (varchar): Nivel de buy-in
- `hash_duplicado` (varchar): Hash para detectar duplicados
- `created_at` (timestamp): Fecha de creación del registro

---

## 🔗 **Relaciones**

### **Relación Principal:**
- `poker_results.user_id` → `users.id` (Foreign Key)
- Un usuario puede tener múltiples resultados
- Un resultado pertenece a un solo usuario

### **Cascada de Eliminación:**
- Al eliminar un usuario, se eliminan todos sus resultados
- Los resultados no pueden existir sin un usuario

---

## 📊 **Índices Recomendados**

```sql
-- Índice para consultas por usuario y fecha
CREATE INDEX idx_poker_results_user_fecha ON poker_results(user_id, fecha DESC);

-- Índice para consultas por usuario y sala
CREATE INDEX idx_poker_results_user_sala ON poker_results(user_id, sala);

-- Índice para consultas por usuario y categoría
CREATE INDEX idx_poker_results_user_categoria ON poker_results(user_id, categoria);

-- Índice para consultas por hash_duplicado (detección de duplicados)
CREATE INDEX idx_poker_results_hash ON poker_results(hash_duplicado);

-- Índice para consultas por usuario y tipo de movimiento
CREATE INDEX idx_poker_results_user_tipo ON poker_results(user_id, tipo_movimiento);
```

---

## 🔍 **Consultas Comunes**

### **1. Obtener estadísticas de un usuario**
```sql
SELECT 
    COUNT(*) as total_registros,
    COUNT(CASE WHEN categoria = 'Torneo' THEN 1 END) as total_torneos,
    SUM(importe) as suma_importes,
    MIN(fecha) as fecha_inicio,
    MAX(fecha) as fecha_fin
FROM poker_results 
WHERE user_id = $1;
```

### **2. Análisis por sala**
```sql
SELECT 
    sala,
    COUNT(*) as registros,
    SUM(importe) as total_importe,
    AVG(importe) as promedio_importe
FROM poker_results 
WHERE user_id = $1 
GROUP BY sala 
ORDER BY total_importe DESC;
```

### **3. Análisis por categoría**
```sql
SELECT 
    categoria,
    COUNT(*) as registros,
    SUM(importe) as total_importe,
    AVG(importe) as promedio_importe
FROM poker_results 
WHERE user_id = $1 
GROUP BY categoria 
ORDER BY total_importe DESC;
```

### **4. Resultados de los últimos N días**
```sql
SELECT 
    fecha,
    SUM(importe) as resultado_dia,
    COUNT(*) as movimientos
FROM poker_results 
WHERE user_id = $1 
    AND fecha >= CURRENT_DATE - INTERVAL '10 days'
    AND categoria NOT IN ('Transferencia', 'Depósito')
    AND tipo_movimiento NOT IN ('Retiro')
GROUP BY fecha 
ORDER BY fecha DESC;
```

### **5. Detectar duplicados**
```sql
SELECT 
    hash_duplicado,
    COUNT(*) as ocurrencias,
    array_agg(id) as ids_duplicados
FROM poker_results 
WHERE user_id = $1 
GROUP BY hash_duplicado 
HAVING COUNT(*) > 1;
```

---

## 🛡️ **Seguridad y Permisos**

### **Row Level Security (RLS)**
```sql
-- Habilitar RLS en poker_results
ALTER TABLE poker_results ENABLE ROW LEVEL SECURITY;

-- Política: Los usuarios solo pueden ver sus propios resultados
CREATE POLICY user_poker_results_policy ON poker_results
    FOR ALL TO authenticated
    USING (user_id = auth.uid());

-- Política: Los administradores pueden ver todos los resultados
CREATE POLICY admin_poker_results_policy ON poker_results
    FOR ALL TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM users 
            WHERE id = auth.uid() AND is_admin = true
        )
    );
```

### **Permisos de Usuario**
```sql
-- Crear rol para usuarios normales
CREATE ROLE poker_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON poker_results TO poker_user;
GRANT SELECT ON users TO poker_user;

-- Crear rol para administradores
CREATE ROLE poker_admin;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO poker_admin;
```

---

## 📈 **Optimizaciones de Rendimiento**

### **1. Particionado por Fecha (Opcional)**
```sql
-- Crear tabla particionada por mes
CREATE TABLE poker_results_y2025m01 PARTITION OF poker_results
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
```

### **2. Estadísticas de Tabla**
```sql
-- Actualizar estadísticas para optimizador de consultas
ANALYZE poker_results;
ANALYZE users;
```

### **3. Configuración de PostgreSQL**
```sql
-- Configuraciones recomendadas para el archivo postgresql.conf
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 4MB
maintenance_work_mem = 64MB
random_page_cost = 1.1
```

---

## 🔄 **Migraciones y Versionado**

### **Migración desde SQLite**
```sql
-- Script para migrar datos desde SQLite a PostgreSQL
-- (Ejecutar después de exportar datos desde SQLite)

-- Insertar usuarios
INSERT INTO users (id, username, email, password_hash, is_admin, created_at)
SELECT 
    gen_random_uuid(),
    username,
    email,
    password_hash,
    is_admin,
    COALESCE(created_at, now())
FROM sqlite_users;

-- Insertar resultados
INSERT INTO poker_results (id, user_id, fecha, hora, descripcion, importe, categoria, tipo_movimiento, tipo_juego, sala, nivel_buyin, hash_duplicado, created_at)
SELECT 
    gen_random_uuid(),
    (SELECT id FROM users WHERE username = sqlite_username),
    fecha,
    hora,
    descripcion,
    importe,
    categoria,
    tipo_movimiento,
    tipo_juego,
    sala,
    nivel_buyin,
    hash_duplicado,
    now()
FROM sqlite_poker_results;
```

---

## 🧪 **Datos de Prueba**

### **Usuario de Prueba**
```sql
INSERT INTO users (id, username, email, password_hash, is_admin, is_active, created_at)
VALUES (
    gen_random_uuid(),
    'testuser',
    'test@example.com',
    '$pbkdf2-sha256$600000$5YKEwNUG0yvY3iC0$bf774d2ce530...',
    true,
    true,
    now()
);
```

### **Resultado de Prueba**
```sql
INSERT INTO poker_results (id, user_id, fecha, hora, descripcion, importe, categoria, tipo_movimiento, tipo_juego, sala, nivel_buyin, hash_duplicado, created_at)
VALUES (
    gen_random_uuid(),
    (SELECT id FROM users WHERE username = 'testuser'),
    '2025-09-26',
    '14:30:00',
    'Tournament #123456 - Hold''em No Limit',
    -11.00,
    'Torneo',
    'Buy In',
    'Hold''em',
    'PokerStars',
    'Micro ($1-$10)',
    'hash_example_123',
    now()
);
```

---

## 📝 **Notas de Implementación**

### **UUIDs vs Enteros**
- **Ventajas**: Únicos globalmente, más seguros, escalables
- **Desventajas**: Mayor tamaño de almacenamiento, índices más lentos
- **Recomendación**: Usar UUIDs para aplicaciones distribuidas

### **Timestamps**
- **Zona Horaria**: Usar `timestamp with time zone` para consistencia
- **Valores por Defecto**: `now()` para created_at, NULL para last_login

### **Validaciones**
- **Email**: Formato válido y único
- **Username**: Alfanumérico, único, longitud mínima
- **Importe**: Precisión decimal (10,2) para monedas
- **Hash Duplicado**: SHA-256 para detección de duplicados

---

## 🚀 **Despliegue en Producción**

### **Variables de Entorno Requeridas**
```bash
DATABASE_URL=postgresql://user:password@host:port/database
SECRET_KEY=your-secret-key-here
FLASK_ENV=production
```

### **Backup y Restauración**
```bash
# Backup
pg_dump -h host -U user -d database > backup.sql

# Restauración
psql -h host -U user -d database < backup.sql
```

### **Monitoreo**
- **Consultas Lentas**: Habilitar `log_min_duration_statement`
- **Conexiones**: Monitorear `max_connections`
- **Espacio**: Verificar `pg_database_size()`

---

## 📚 **Referencias**

- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [SQLAlchemy PostgreSQL](https://docs.sqlalchemy.org/en/14/dialects/postgresql.html)
- [UUID Best Practices](https://www.postgresql.org/docs/current/datatype-uuid.html)
- [Row Level Security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)

---

**📅 Última actualización**: 26 de Septiembre de 2025  
**🔧 Versión**: 1.0  
**👨‍💻 Mantenido por**: Equipo de Desarrollo Poker Results API

