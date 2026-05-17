#!/bin/bash
set -e

cd /opt/render/project/src/backend

python -m src.worker.main &
python -m src.janitor.main &

exec uvicorn src.api.main:app --host 0.0.0.0 --port $PORT
