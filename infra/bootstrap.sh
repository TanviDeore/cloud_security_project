#!/usr/bin/env bash
# Provisions every "AWS" resource in LocalStack.
# Idempotent: safe to re-run.
set -euo pipefail

cd "$(dirname "$0")"

# Auto-activate the project venv so awslocal is on PATH (running this from
# a fresh shell would otherwise miss it even if `pip install` was done).
if [ -f ../.venv/bin/activate ] && [ -z "${VIRTUAL_ENV:-}" ]; then
  # shellcheck disable=SC1091
  . ../.venv/bin/activate
fi

# Load .env if present
if [ -f ../.env ]; then set -a; . ../.env; set +a; fi

if ! command -v awslocal >/dev/null 2>&1; then
  echo "ERROR: 'awslocal' not found on PATH." >&2
  echo "       Activate the venv first: source .venv/bin/activate" >&2
  echo "       and ensure 'pip install -r requirements.txt' has been run." >&2
  exit 1
fi

export AWS_ENDPOINT_URL=${AWS_ENDPOINT_URL:-http://localhost:4566}
export AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION:-us-east-1}
export AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID:-test}
export AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY:-test}

echo "==> Waiting for LocalStack..."
for i in {1..30}; do
  if curl -fsS "${AWS_ENDPOINT_URL}/_localstack/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

echo "==> Creating KMS CMK (symmetric, envelope encryption)"
bash ./create_kms_key.sh

echo "==> Creating KMS signing key (asymmetric, PDF signatures)"
bash ./create_signer_key.sh

echo "==> Creating S3 bucket"
bash ./create_s3_bucket.sh

echo "==> Creating DynamoDB tables (Ledger, Policies, Users, Notifications)"
bash ./create_dynamodb_tables.sh

echo "==> Creating Secrets Manager entry"
bash ./create_secrets.sh

echo "==> Identity backend (Cognito if available; fallback file)"
bash ./create_cognito_pool.sh

echo "==> Seeding users (admin + demo accounts)"
bash ./seed_users.sh

echo "==> Deploying Lambdas"
bash ./deploy_lambdas.sh

echo "==> Creating API Gateway"
bash ./create_api_gateway.sh

echo "==> Creating CloudWatch alarm"
bash ./create_cloudwatch_alarm.sh

echo
echo "Bootstrap complete."
