#!/usr/bin/env bash
# Tears down LocalStack state and re-bootstraps everything.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")"/.. && pwd)"
cd "$ROOT"

docker compose down -v
rm -rf .localstack
docker compose up -d

echo "Waiting for LocalStack..."
for i in {1..60}; do
  if curl -fsS http://localhost:4566/_localstack/health >/dev/null 2>&1; then break; fi
  sleep 1
done

bash infra/bootstrap.sh
python scripts/seed_records.py
echo
echo "Reset complete. Run: python -m app.main"
