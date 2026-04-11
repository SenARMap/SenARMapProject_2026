#!/bin/sh
if [ "$1" = "renew" ]; then
    docker compose up -d --build
else
    docker compose up -d
fi

docker exec -it iki_project_2026 /bin/bash