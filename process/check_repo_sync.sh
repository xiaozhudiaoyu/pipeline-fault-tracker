#!/usr/bin/env bash
set -u
echo "---repo real path---"
ls -ld /home/xiaozhu/pipeline-fault-tracker
readlink -f /home/xiaozhu/pipeline-fault-tracker
echo "---migration file in repo---"
grep -c postgresql /home/xiaozhu/pipeline-fault-tracker/backend/alembic/versions/b3e19c4d7a52_add_priority_to_pipeline_faults.py
echo "---mtime---"
ls -l /home/xiaozhu/pipeline-fault-tracker/backend/alembic/versions/
echo "---git status---"
cd /home/xiaozhu/pipeline-fault-tracker && git status --short && git log --oneline -3
