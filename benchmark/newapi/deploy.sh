#!/usr/bin/env bash
# NewAPI 单机部署（4 核 8G 建议）：PostgreSQL + Redis + NewAPI
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ ! -f .env ]]; then
  echo "Creating .env from .env.example (please change POSTGRES_PASSWORD in production)"
  cp -n .env.example .env
fi

mkdir -p data logs
echo "Starting NewAPI stack..."
docker compose up -d

echo "Waiting for NewAPI to be healthy..."
for i in {1..30}; do
  if curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/api/status | grep -q 200; then
    echo "NewAPI is up at http://localhost:3000"
    exit 0
  fi
  sleep 2
done
echo "NewAPI may still be starting; check http://localhost:3000"
