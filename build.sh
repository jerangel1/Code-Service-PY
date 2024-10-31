#!/bin/bash
echo "Building"
docker compose -p code_service build
echo "Shutting Down"
docker compose -p code_service down
echo "Starting"
docker compose -p code_service up -d --force-recreate
echo "Deleting Unused Images"
if [ -n "$dangling_images" ]; then
  docker rmi $dangling_images -f
else
  echo "No dangling images to delete."
fi


