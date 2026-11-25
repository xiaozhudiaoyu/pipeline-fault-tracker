#!/usr/bin/env bash
set -u
echo "---enum types---"
docker exec pipeline-fault-tracker-postgres-1 psql -U pft -d pft -Atc "SELECT typname FROM pg_type WHERE typcategory='E';"
echo "---tables---"
docker exec pipeline-fault-tracker-postgres-1 psql -U pft -d pft -Atc "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1;"
echo "---alembic_version---"
docker exec pipeline-fault-tracker-postgres-1 psql -U pft -d pft -Atc "SELECT version_num FROM alembic_version;"
echo "---faultpriority attrs---"
docker exec pipeline-fault-tracker-postgres-1 psql -U pft -d pft -Atc "SELECT enumlabel FROM pg_enum e JOIN pg_type t ON t.oid=e.enumtypid WHERE t.typname='faultpriority';"
