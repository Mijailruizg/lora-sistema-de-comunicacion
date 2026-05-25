# Sistema de Comunicación LoRa

Este es un sistema de simulación y comunicación LoRa desarrollado con Django.

## Descripción

Proyecto para simular y analizar características de comunicación LoRa, incluyendo pérdida de propagación, estado de Fresnel y otros parámetros de la propagación de ondas.

## Requisitos

- Python 3.x
- Django
- (Ver requirements.txt para dependencias completas)

## Instalación

1. Clonar el repositorio
2. Crear un ambiente virtual: `python -m venv venv`
3. Activar el ambiente virtual:
   - Windows: `venv\Scripts\activate`
   - Linux/Mac: `source venv/bin/activate`
4. Instalar dependencias: `pip install -r requirements.txt`
5. Ejecutar migraciones: `python manage.py migrate`
6. Iniciar el servidor: `python manage.py runserver`

## Uso

Acceder a `http://localhost:8000` en tu navegador.

## Estructura del Proyecto

- `simulator/` - Aplicación principal
  - `models.py` - Modelos de datos
  - `views.py` - Vistas
  - `propagation_engine.py` - Motor de simulación de propagación
  - `templates/` - Plantillas HTML
  - `static/` - Archivos estáticos (CSS, JS)

## Licencia

(Especificar si es necesario)
