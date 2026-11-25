#!/usr/bin/env bash
set -u
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
echo "=== compose ps ==="
cd /home/xiaozhu/pipeline-fault-tracker && docker compose -f docker-compose.yml -f docker-compose.pg.yml ps
echo "=== frontend probe ==="
tr -d '\r' < '/mnt/e/python项目/pipeline-fault-tracker/process/probe_frontend_inner.sh' > /tmp/probe_inner.sh
docker cp /tmp/probe_inner.sh pipeline-fault-tracker-frontend-1:/tmp/probe.sh
docker exec pipeline-fault-tracker-frontend-1 sh /tmp/probe.sh
