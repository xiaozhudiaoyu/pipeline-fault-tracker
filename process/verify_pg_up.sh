#!/usr/bin/env bash
set -u
echo "=== 1. backend migration log ==="
docker logs pipeline-fault-tracker-backend-1 2>&1 | grep -E "Running upgrade|entrypoint|Uvicorn|Application startup"
echo "=== 2. docker ps ==="
docker ps --format 'table {{.Names}}\t{{.Status}}'
echo "=== 3. alembic_version in PG ==="
docker exec pipeline-fault-tracker-postgres-1 psql -U pft -d pft -Atc "SELECT version_num FROM alembic_version;"
echo "=== 4. enum types / tables / boolean defaults ==="
docker exec pipeline-fault-tracker-postgres-1 psql -U pft -d pft -Atc "SELECT typname FROM pg_type WHERE typcategory='E' ORDER BY 1;"
docker exec pipeline-fault-tracker-postgres-1 psql -U pft -d pft -Atc "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1;"
docker exec pipeline-fault-tracker-postgres-1 psql -U pft -d pft -Atc "SELECT column_name, data_type, column_default FROM information_schema.columns WHERE table_name='users' AND column_name IN ('is_active','role');"
