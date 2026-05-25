# Guía de Deployment en Render

## Pasos para enlazar tu proyecto con Render

### 1. Crear cuenta en Render
- Ve a https://render.com y crea una cuenta gratuita
- Vincula tu cuenta de GitHub

### 2. Conectar el repositorio
1. En el dashboard de Render, click en "New +"
2. Selecciona "Web Service"
3. En "Connect a repository", busca `lora-sistema-de-comunicacion`
4. Selecciona el repositorio y autoriza si es necesario

### 3. Configurar el Web Service
1. **Name**: `lora-simulator` (o el nombre que prefieras)
2. **Environment**: Python 3
3. **Region**: Selecciona la más cercana a ti
4. **Branch**: `main`
5. **Build Command**: `./build.sh`
6. **Start Command**: `gunicorn lora_project.wsgi:application`
7. **Plan**: Free (o el que prefieras)

### 4. Configurar variables de entorno
En la sección "Environment", agrega las siguientes variables:

| Key | Value |
|-----|-------|
| `DEBUG` | `False` |
| `SECRET_KEY` | Genera una clave segura [aquí](https://djecrety.ir/) |
| `ALLOWED_HOSTS` | `tu-app.onrender.com` |
| `PYTHON_VERSION` | `3.11` |

### 5. Deploy automático
- Render detectará automáticamente el archivo `render.yaml`
- Cada push a `main` disparará un nuevo deployment automáticamente

### 6. URL de tu aplicación
Una vez deployada, tu app estará en:
```
https://tu-nombre-app.onrender.com
```

## Archivos de configuración creados

- **render.yaml** - Configuración principal de Render
- **build.sh** - Script de construcción (migraciones, archivos estáticos)
- **requirements.txt** - Dependencias de Python actualizadas
- **.env.example** - Ejemplo de variables de entorno
- **settings.py** - Actualizado para producción (WhiteNoise, variables de entorno)

## Notas importantes

- La base de datos SQLite en Render es efímera (se reinicia en cada deploy)
- Para producción, considera usar PostgreSQL
- WhiteNoise sirve automáticamente los archivos estáticos
- Los logs estarán disponibles en el dashboard de Render

¡Tu proyecto está listo para desplegar! 🚀
