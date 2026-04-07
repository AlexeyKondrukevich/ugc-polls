#!/bin/bash

docker compose  --env-file ./.env -f ./docker-compose.prod.yml --project-name ugc_polls up -d "$@"