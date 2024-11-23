#!/bin/bash
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${GREEN}🚀 Iniciando entorno de desarrollo...${NC}"

# Ejecutar solo el servicio principal con recarga automática
docker compose -p code_service up app --build

# El servicio se ejecutará en primer plano y mostrará logs