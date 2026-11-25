#!/usr/bin/env bash
# P3 验证脚本：SQLite → PostgreSQL 迁移后的全闭环冒烟（在 WSL 内、compose 项目根目录执行）。
# 前置：docker compose up -d --build 已起且三容器 healthy。
# 用法：bash process/verify_p3.sh
# 说明：API 经 frontend 的 nginx 反代 localhost:8080/api -> backend:8000；无需 backend 单独发布端口。

set -u
API="localhost:8080/api"
CODE="LINE-PG-$RANDOM"   # 随机 code，避免重复运行撞 409

echo "=== 0) 前端 SPA 是否由 nginx 正常提供服务 ==="
curl -s -o /dev/null -w 'GET / -> HTTP %{http_code}\n' localhost:8080/

echo "=== 1) 创建流水线 POST /api/pipelines ==="
PIPE=$(curl -s -X POST "$API/pipelines" -H 'Content-Type: application/json' \
  -d "{\"code\":\"$CODE\",\"name\":\"PG验证线\",\"description\":\"P3 全闭环冒烟\"}")
echo "$PIPE"
PID=$(printf '%s' "$PIPE" | grep -o '"id":[0-9]\+' | head -1 | grep -o '[0-9]\+')
echo "pipeline_id=$PID"

echo "=== 2) 登记故障 POST /api/faults ==="
FAULT=$(curl -s -X POST "$API/faults" -H 'Content-Type: application/json' \
  -d "{\"pipeline_id\":$PID,\"location\":\"3号工位传送带\",\"occurred_at\":\"2026-09-01T08:00:00\",\"symptom\":\"传送带异响并突然停机\"}")
echo "$FAULT"
FID=$(printf '%s' "$FAULT" | grep -o '"id":[0-9]\+' | head -1 | grep -o '[0-9]\+')
echo "fault_id=$FID"

echo "=== 3) 列表 GET /api/faults ==="
curl -s "$API/faults?page=1&size=20"; echo ''

echo "=== 4) 详情 GET /api/faults/$FID ==="
curl -s "$API/faults/$FID"; echo ''

echo "=== 5) 修改基础信息 PATCH /api/faults/$FID（location）==="
curl -s -X PATCH "$API/faults/$FID" -H 'Content-Type: application/json' \
  -d '{"location":"5号工位电机段"}'; echo ''

echo "=== 6a) 状态推进 pending -> processing ==="
curl -s -X PATCH "$API/faults/$FID/transition" -H 'Content-Type: application/json' \
  -d '{"target_status":"processing"}'; echo ''

echo "=== 6b) 状态推进 processing -> done（handling_note 必填）==="
curl -s -X PATCH "$API/faults/$FID/transition" -H 'Content-Type: application/json' \
  -d '{"target_status":"done","handling_note":"更换电机后恢复正常运行"}'; echo ''

echo "=== 7) 错误路径：done 不可逆 -> 期望 409 ==="
curl -s -o /dev/null -w 'HTTP %{http_code}（期望 409）\n' -X PATCH "$API/faults/$FID/transition" \
  -H 'Content-Type: application/json' -d '{"target_status":"pending"}'

echo "=== 8) 错误路径：重复 code -> 期望 409 ==="
curl -s -o /dev/null -w 'HTTP %{http_code}（期望 409）\n' -X POST "$API/pipelines" \
  -H 'Content-Type: application/json' -d "{\"code\":\"$CODE\",\"name\":\"重复线\"}"

echo "=== 9) 错误路径：非法枚举 status -> 期望 422 ==="
curl -s -o /dev/null -w 'HTTP %{http_code}（期望 422）\n' "$API/faults?status=not_a_status"

echo "=== 10) PG 落库确认（数据真的写进 PostgreSQL）==="
docker compose exec -T postgres psql -U pft -d pft -c "SELECT id,code,name FROM pipelines WHERE code='$CODE';"
docker compose exec -T postgres psql -U pft -d pft -c "SELECT id,pipeline_id,status,location,closed_at FROM pipeline_faults WHERE id=$FID;"

echo "=== 11) 计数（供 down/up 持久化对比）==="
docker compose exec -T postgres psql -U pft -d pft -tA -c "SELECT 'pipelines='||count(*) FROM pipelines;"
docker compose exec -T postgres psql -U pft -d pft -tA -c "SELECT 'faults='||count(*) FROM pipeline_faults;"
