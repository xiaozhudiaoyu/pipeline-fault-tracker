#!/usr/bin/env bash
set -e
cd ~ && cd pipeline-fault-tracker
echo "=== step1: down ==="
docker compose -f docker-compose.yml -f docker-compose.pg.yml down
echo "=== step2: rm volume ==="
docker volume rm pipeline-fault-tracker_pft-pgdata
echo "=== step3: up -d --build ==="
docker compose -f docker-compose.yml -f docker-compose.pg.yml up -d --build
echo "=== done ==="
