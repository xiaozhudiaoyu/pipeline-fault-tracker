#!/usr/bin/env bash
# Verify the timezone fix under a UTC process (the backend container default).
# Mounts the working-tree app/ over the image copy, read-only, and runs the probe
# script inside a throwaway container: no service started, no DB touched.
set -euo pipefail
cd "$(dirname "$0")/.."

IMAGE=pipeline-fault-tracker-backend

echo "=== baseline: image code as built (pre-fix), process timezone = UTC ==="
docker run --rm \
  -e TZ=UTC \
  -e PYTHONPATH=/app \
  -v "$PWD/process/_verify_tz_container.py:/verify.py:ro" \
  --entrypoint sh "$IMAGE" \
  -c 'uv run --no-sync python /verify.py' 2>&1

echo

echo "=== process timezone = UTC (container default, fix under test) ==="
docker run --rm \
  -e TZ=UTC \
  -e PYTHONPATH=/app \
  -v "$PWD/backend/app:/app/app:ro" \
  -v "$PWD/process/_verify_tz_container.py:/verify.py:ro" \
  --entrypoint sh "$IMAGE" \
  -c 'uv run --no-sync python /verify.py' 2>&1

echo
echo "=== process timezone = Asia/Shanghai (what the compose TZ setting yields) ==="
docker run --rm \
  -e TZ=Asia/Shanghai \
  -e PYTHONPATH=/app \
  -v "$PWD/backend/app:/app/app:ro" \
  -v "$PWD/process/_verify_tz_container.py:/verify.py:ro" \
  --entrypoint sh "$IMAGE" \
  -c 'uv run --no-sync python /verify.py' 2>&1
