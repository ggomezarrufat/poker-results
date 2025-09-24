# Poker Results - Despliegue en Vercel con Supabase

## 🚀 Configuración para Despliegue

### 1. Configuración de Supabase

#### Crear Proyecto en Supabase:
1. Ve a [supabase.com](https://supabase.com)
2. Crea una nueva cuenta o inicia sesión
3. Crea un nuevo proyecto
4. Anota la URL y la API Key

#### Configurar Base de Datos:
1. Ve al SQL Editor en Supabase
2. Ejecuta el script `supabase_setup.sql`
3. Verifica que las tablas se crearon correctamente

### 2. Configuración de Variables de Entorno

#### Variables Requeridas:
```bash
SECRET_KEY=tu_clave_secreta_muy_segura_aqui
SUPABASE_URL=tu_url_de_supabase
SUPABASE_KEY=tu_clave_de_supabase
DATABASE_URL=postgresql://usuario:password@host:puerto/database
```

#### En Vercel:
1. Ve a tu proyecto en Vercel
2. Settings → Environment Variables
3. Agrega todas las variables de entorno

### 3. Despliegue en Vercel

#### Opción 1: Desde GitHub
1. Conecta tu repositorio de GitHub a Vercel
2. Selecciona la rama `vercel`
3. Vercel detectará automáticamente la configuración

#### Opción 2: Desde CLI
```bash
# Instalar Vercel CLI
npm i -g vercel

# Login en Vercel
vercel login

# Desplegar
vercel --prod
```

### 4. Configuración Post-Despliegue

#### Inicializar Base de Datos:
1. Accede a tu aplicación desplegada
2. Ve a `/init-db` (endpoint de inicialización)
3. Esto creará el usuario administrador por defecto

#### Credenciales por Defecto:
- **Usuario**: admin
- **Contraseña**: admin123
- **⚠️ IMPORTANTE**: Cambiar la contraseña inmediatamente

### 5. Estructura del Proyecto

```
poker-results/
├── app_multiusuario.py          # Aplicación principal
├── init_db.py                   # Script de inicialización
├── requirements.txt             # Dependencias Python
├── vercel.json                 # Configuración Vercel
├── supabase_setup.sql          # Script de configuración Supabase
├── env.example                 # Variables de entorno ejemplo
├── templates/                  # Plantillas HTML
│   ├── base_multiusuario.html
│   ├── login.html
│   ├── admin.html
│   └── ...
└── static/                     # Archivos estáticos
```

### 6. Características del Sistema Multiusuario

#### 🔐 Autenticación:
- Login/logout con Flask-Login
- Sesiones seguras
- Recordar usuario opcional

#### 👥 Gestión de Usuarios:
- Usuarios regulares y administradores
- Activación/desactivación de usuarios
- Cambio de contraseñas

#### 📊 Análisis por Usuario:
- Cada usuario ve solo sus datos
- Administradores pueden ver análisis de cualquier usuario
- Filtros y reportes personalizados

#### 🛡️ Seguridad:
- Row Level Security (RLS) en Supabase
- Políticas de acceso por usuario
- Validación de permisos en cada endpoint

### 7. Endpoints Principales

#### Públicos:
- `/login` - Página de login
- `/logout` - Cerrar sesión

#### Protegidos (Requieren login):
- `/` - Página principal
- `/importar` - Importar archivos
- `/informes` - Generar informes
- `/analisis` - Análisis avanzado

#### Administración (Solo admins):
- `/admin` - Panel de administración
- `/admin/users` - Gestión de usuarios
- `/admin/analisis` - Análisis por usuario

### 8. API Endpoints

#### Importación:
- `POST /api/importar` - Importar archivos Excel/HTML

#### Informes:
- `GET /api/informes/resultados` - Obtener resultados
- `GET /api/informes/opciones` - Obtener opciones de filtros

#### Análisis:
- `GET /api/analisis/insights` - Análisis avanzado

#### Administración:
- `GET /api/admin/users` - Listar usuarios
- `POST /api/admin/users` - Crear usuario
- `PUT /api/admin/users/<id>` - Actualizar usuario
- `DELETE /api/admin/users/<id>` - Eliminar usuario

### 9. Migración de Datos Existentes

Si tienes datos en SQLite local:

```python
# Script de migración (ejecutar localmente)
from app_multiusuario import app, db, User, PokerResult
import sqlite3

def migrate_data():
    with app.app_context():
        # Conectar a SQLite local
        conn = sqlite3.connect('instance/poker_results.db')
        cursor = conn.cursor()
        
        # Obtener datos existentes
        cursor.execute("SELECT * FROM poker_result")
        results = cursor.fetchall()
        
        # Crear usuario por defecto para datos existentes
        default_user = User(
            username='migrated_user',
            email='migrated@poker-results.com',
            is_admin=False,
            is_active=True
        )
        default_user.set_password('temp_password')
        db.session.add(default_user)
        db.session.commit()
        
        # Migrar datos
        for result in results:
            new_result = PokerResult(
                user_id=default_user.id,
                fecha=result[1],
                hora=result[2],
                descripcion=result[3],
                importe=result[4],
                categoria=result[5],
                tipo_movimiento=result[6],
                tipo_juego=result[7],
                sala=result[8],
                nivel_buyin=result[9],
                hash_duplicado=result[10]
            )
            db.session.add(new_result)
        
        db.session.commit()
        print("Migración completada")

if __name__ == '__main__':
    migrate_data()
```

### 10. Monitoreo y Mantenimiento

#### Logs:
- Vercel proporciona logs automáticamente
- Revisar logs en el dashboard de Vercel

#### Backup:
- Supabase realiza backups automáticos
- Configurar backup manual si es necesario

#### Actualizaciones:
- Actualizar dependencias regularmente
- Monitorear seguridad de la aplicación

### 11. Troubleshooting

#### Problemas Comunes:

1. **Error de conexión a Supabase**:
   - Verificar variables de entorno
   - Comprobar URL y API Key

2. **Error de permisos**:
   - Verificar políticas RLS en Supabase
   - Comprobar configuración de autenticación

3. **Error de importación**:
   - Verificar tamaño de archivos
   - Comprobar formato de archivos

4. **Error de memoria**:
   - Optimizar consultas
   - Implementar paginación

### 12. Seguridad

#### Mejores Prácticas:
- Cambiar contraseñas por defecto
- Usar HTTPS (automático en Vercel)
- Configurar CORS apropiadamente
- Monitorear accesos sospechosos

#### Configuración de Seguridad:
- Row Level Security habilitado
- Validación de entrada en todos los endpoints
- Sanitización de datos
- Rate limiting (configurar en Vercel)

### 13. Escalabilidad

#### Optimizaciones:
- Índices de base de datos
- Caché de consultas frecuentes
- Compresión de respuestas
- CDN para archivos estáticos

#### Monitoreo:
- Métricas de rendimiento
- Alertas de errores
- Monitoreo de uso de recursos

---

## 🎯 Resumen de Despliegue

1. **Configurar Supabase** → Ejecutar `supabase_setup.sql`
2. **Configurar Vercel** → Variables de entorno
3. **Desplegar** → Conectar repositorio o usar CLI
4. **Inicializar** → Crear usuario administrador
5. **Configurar** → Cambiar contraseñas por defecto
6. **Migrar** → Datos existentes (si aplica)

¡Tu aplicación estará lista para producción! 🚀
