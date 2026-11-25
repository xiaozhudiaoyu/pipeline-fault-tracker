# Diagnostic: PG state inside pipeline-fault-tracker-postgres-1
$q1 = "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1;"
$q2 = "SELECT count(*) FROM pipelines;"
docker exec pipeline-fault-tracker-postgres-1 psql -U pft -d pft -Atc $q1
Write-Output "---rows---"
docker exec pipeline-fault-tracker-postgres-1 psql -U pft -d pft -Atc $q2
Write-Output "---volumes---"
docker volume ls
Write-Output "---backend entrypoint head---"
docker exec pipeline-fault-tracker-backend-1 head -40 /app/entrypoint.sh 2>$null
