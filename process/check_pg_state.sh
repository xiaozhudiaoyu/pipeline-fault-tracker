#!/usr/bin/env bash
set -u
echo "---tables---"
docker exec pipeline-fault-tracker-postgres-1 psql -U pft -d pft -Atc "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1;"
echo "---pipelines rows---"
docker exec pipeline-fault-tracker-postgres-1 psql -U pft -d pft -Atc "SELECT count(*) FROM pipelines;"
echo "---volumes---"
docker volume ls
echo "---backend entrypoint---"
docker run --rm --entrypoint cat pipeline-fault-tracker-backend /app/entrypoint.sh
echo "---alembic versions in image---"
docker run --rm --entrypoint ls pipeline-fault-tracker-backend -la /app/alembic/versions/
echo "---columns check---"
docker exec pipeline-fault-tracker-postgres-1 psql -U pft -d pft -Atc "SELECT table_name FROM information_schema.columns WHERE table_schema='public' AND column_name='priority';"
echo "---row counts---"
docker exec pipeline-fault-tracker-postgres-1 psql -U pft -d pft -Atc "SELECT 'faults', count(*) FROM pipeline_faults UNION ALL SELECT 'timelines', count(*) FROM fault_timelines;"
echo "---pipeline_faults columns---"
docker exec pipeline-fault-tracker-postgres-1 psql -U pft -d pft -Atc "SELECT column_name FROM information_schema.columns WHERE table_name='pipeline_faults' ORDER BY ordinal_position;"
