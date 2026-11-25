#!/usr/bin/env bash
set -eu
WIN="/mnt/e/python项目/pipeline-fault-tracker/backend/alembic/versions"
WSL="/home/xiaozhu/pipeline-fault-tracker/backend/alembic/versions"
for f in b3e19c4d7a52_add_priority_to_pipeline_faults.py 105a10b2f697_phase3_add_users_timelines_and_fault_.py; do
echo "=== port $f ==="
tr -d '\r' < "$WIN/$f" > "$WSL/$f"
diff <(tr -d '\r' < "$WIN/$f") "$WSL/$f" && echo "IN_SYNC"
done
