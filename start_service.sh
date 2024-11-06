#!/bin/bash

echo "🚀 Iniciando servicio..."

# Cargar variables de entorno
source .env
echo "📚 Variables de entorno cargadas"

# Mostrar configuración
echo "🔧 Configuración:"
echo "- Workers: $WORKERS"
echo "- Puerto: $API_PORT"
echo "- Orígenes permitidos: $ALLOWED_ORIGINS"

# Iniciar uvicorn con logging mejorado
uvicorn main:app \
    --workers $WORKERS \
    --host 0.0.0.0 \
    --port $API_PORT \
    --log-level debug \
    --reload \
    --access-log \
    --use-colors

# Si el servicio se detiene
echo "👋 Servicio detenido"