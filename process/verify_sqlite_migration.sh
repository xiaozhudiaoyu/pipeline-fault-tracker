#!/usr/bin/env bash
set -u
cat > /tmp/sqlite_check.sh <<'EOF'
set -e
uv run --no-sync alembic upgrade head 2>&1 | tail -n 6
python3 - <<'PYEOF'
import sqlite3
c = sqlite3.connect("/tmp/t.db")
for name in ("users", "fault_timelines", "pipeline_faults"):
    sql = c.execute("SELECT sql FROM sqlite_master WHERE name=?", (name,)).fetchone()[0]
    for line in sql.splitlines():
        if "is_active" in line or "is_imported" in line or "priority" in line or "role " in line:
            print(name, "::", line.strip())
print("alembic_version:", c.execute("SELECT version_num FROM alembic_version").fetchone()[0])
PYEOF
EOF
docker run --rm -e DATABASE_URL=sqlite:////tmp/t.db \
  -v /home/xiaozhu/pipeline-fault-tracker/backend/alembic:/app/alembic \
  -v /home/xiaozhu/pipeline-fault-tracker/backend/alembic.ini:/app/alembic.ini \
  -v /tmp/sqlite_check.sh:/tmp/check.sh \
  --entrypoint sh pipeline-fault-tracker-backend /tmp/check.sh
