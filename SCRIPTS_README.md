# Scripts de Inicio y Gestión - Poker Results

Este directorio contiene scripts bash para facilitar el inicio y gestión de la aplicación Poker Results.

## 📋 Scripts Disponibles

### 🚀 `start_app.sh` - Inicio Completo
Script principal para iniciar la aplicación con todas las verificaciones.

**Características:**
- ✅ Verifica que estés en el directorio correcto
- ✅ Verifica la existencia del entorno virtual
- ✅ Verifica la configuración del archivo `.env`
- ✅ Activa automáticamente el entorno virtual
- ✅ Instala dependencias si es necesario
- ✅ Verifica la conexión a Supabase
- ✅ Inicia la aplicación con mensajes informativos

**Uso:**
```bash
./start_app.sh
```

### ⚡ `start_dev.sh` - Inicio Rápido
Script simplificado para desarrollo rápido.

**Características:**
- ⚡ Inicio rápido sin verificaciones
- 🎯 Ideal para desarrollo cuando ya sabes que todo está configurado

**Uso:**
```bash
./start_dev.sh
```

### 🛑 `stop_app.sh` - Parada de la Aplicación
Script para detener la aplicación de manera segura.

**Características:**
- 🔍 Busca procesos de la aplicación ejecutándose
- 📤 Envía señal TERM (terminación suave)
- 💀 Fuerza terminación si es necesario
- 🔌 Libera el puerto 5001

**Uso:**
```bash
./stop_app.sh
```

## 🔧 Configuración Previa

Antes de usar estos scripts, asegúrate de tener:

1. **Entorno virtual creado:**
   ```bash
   python -m venv venv
   ```

2. **Dependencias instaladas:**
   ```bash
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Archivo `.env` configurado:**
   ```bash
   cp env.example .env
   # Edita .env con tus credenciales de Supabase
   ```

## 📱 Acceso a la Aplicación

Una vez iniciada la aplicación:
- 🌐 **URL:** http://localhost:5001
- 👤 **Usuario admin:** admin / admin123 (por defecto)

## 🚨 Solución de Problemas

### Error: "No se encontró app_multiusuario_working.py"
- Asegúrate de ejecutar el script desde el directorio raíz del proyecto

### Error: "No se encontró el entorno virtual 'venv'"
- Crea el entorno virtual: `python -m venv venv`

### Error: "No se encontró el archivo .env"
- Copia el archivo de ejemplo: `cp env.example .env`
- Configura las variables de Supabase en `.env`

### Error de conexión a Supabase
- Verifica que `SUPABASE_URL` y `SUPABASE_KEY` estén correctamente configurados en `.env`
- Asegúrate de que tu proyecto de Supabase esté activo

### Puerto 5001 en uso
- Usa `./stop_app.sh` para detener procesos existentes
- O cambia el puerto en `app_multiusuario_working.py`

## 📝 Notas

- Los scripts están configurados para macOS/Linux
- En Windows, usa Git Bash o WSL para ejecutar estos scripts
- Para desarrollo, puedes usar `start_dev.sh` para un inicio más rápido
- Para producción, usa `start_app.sh` para verificaciones completas
