#!/usr/bin/env bash
# P3 持久化验证：down（不带 -v，保留 named volume pft-pgdata）-> up -> 数据仍在。
# 用法：bash process/verify_p3_persist.sh （WSL 内、compose 根目录）
set -u

count() {
  echo -n "pipelines="; docker compose exec -T postgres psql -U pft -d pft -tA -c "SELECT count(*) FROM pipelines;"
  echo -n "faults=";    docker compose exec -T postgres psql -U pft -d pft -tA -c "SELECT count(*) FROM pipeline_faults;"
}

echo "=== 1) 基线计数（down 前）==="
count

echo "=== 2) docker compose down（保留 named volume）==="
docker compose down

echo "=== 3) 确认卷 pft-pgdata 仍存在（down 未删卷）==="
docker volume ls | grep pft-pgdata || echo "!! 卷不存在（异常）"

echo "=== 4) docker compose up -d（复用已构建镜像，不 --build）==="
docker compose up -d

echo "=== 5) 等待 backend 健康（最多 ~60s）==="
for i in $(seq 1 30); do
  st=$(docker compose ps --format '{{.Service}} {{.Health}}' 2>/dev/null | grep '^backend' | awk '{print $2}')
  if [ "$st" = "healthy" ]; then echo "backend healthy（第 ${i} 次探测）"; break; fi
  sleep 2
done
docker compose ps

echo "=== 6) 重新计数（应与基线一致 = 数据在 named volume 中持久化）==="
count

echo "=== 7) 经 API 复核列表仍有数据 ==="
curl -s "localhost:8080/api/faults?page=1&size=20" -o /dev/null -w 'GET /api/faults -> HTTP %{http_code}\n'
curl -s "localhost:8080/api/faults?page=1&size=20" | grep -o '"total":[0-9]\+'
