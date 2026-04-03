#!/bin/bash

docker compose  --env-file ./.env -f ./docker-compose.yml --project-name ugc_polls up -d "$@"