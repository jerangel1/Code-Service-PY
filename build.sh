#!/bin/bash

# Colores para los mensajes
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}🔍 Ejecutando verificaciones de código...${NC}"
docker compose -p code_service run --rm lint
LINT_EXIT_CODE=$?

if [ $LINT_EXIT_CODE -ne 0 ]; then
    echo -e "${RED}❌ Las verificaciones de código fallaron${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Verificaciones de código exitosas${NC}"

echo -e "${GREEN}🧪 Ejecutando tests...${NC}"
docker compose -p code_service run --rm test
TEST_EXIT_CODE=$?

if [ $TEST_EXIT_CODE -ne 0 ]; then
    echo -e "${RED}❌ Los tests fallaron${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Tests exitosos${NC}"

echo -e "${GREEN}🏗️ Construyendo la aplicación...${NC}"
docker compose -p code_service build app

echo -e "${GREEN}🔄 Reiniciando servicios...${NC}"
docker compose -p code_service down
docker compose -p code_service up -d --force-recreate

echo -e "${GREEN}🧹 Limpiando imágenes no utilizadas...${NC}"
dangling_images=$(docker images -f "dangling=true" -q)
if [ -n "$dangling_images" ]; then
    docker rmi $dangling_images -f
    echo -e "${GREEN}✨ Imágenes no utilizadas eliminadas${NC}"
else
    echo -e "${GREEN}✨ No hay imágenes para limpiar${NC}"
fi

echo -e "${GREEN}🚀 Servicio desplegado exitosamente${NC}"

# Mostrar logs
echo -e "${GREEN}📋 Mostrando logs...${NC}"
docker compose -p code_service logs -f app