#!/usr/bin/env bash
# Packages and deploys the smart-contract + audit-appender Lambdas to LocalStack.
# We bundle the cloud/ package into the deployment zip so Lambdas can use the
# same wrappers the Flask app uses.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")"/.. && pwd)"
cd "$ROOT"

REGION=${AWS_DEFAULT_REGION:-us-east-1}
ROLE_ARN="arn:aws:iam::000000000000:role/lambda-role"

deploy() {
  local NAME=$1
  local SRC_DIR=$2
  local ZIP="/tmp/${NAME}.zip"
  rm -f "$ZIP"
  TMPDIR=$(mktemp -d)
  cp -R "$SRC_DIR"/. "$TMPDIR"/
  cp -R cloud "$TMPDIR/cloud"
  (cd "$TMPDIR" && zip -qr "$ZIP" .)
  rm -rf "$TMPDIR"

  if aws --endpoint-url "$AWS_ENDPOINT_URL" lambda get-function --function-name "$NAME" >/dev/null 2>&1; then
    aws --endpoint-url "$AWS_ENDPOINT_URL" lambda update-function-code \
      --function-name "$NAME" --zip-file "fileb://$ZIP" >/dev/null
    echo "Updated Lambda $NAME"
  else
    aws --endpoint-url "$AWS_ENDPOINT_URL" lambda create-function \
      --function-name "$NAME" \
      --runtime python3.11 \
      --role "$ROLE_ARN" \
      --handler handler.lambda_handler \
      --zip-file "fileb://$ZIP" \
      --timeout 15 \
      --environment "Variables={AWS_ENDPOINT_URL=http://localstack:4566,KMS_KEY_ALIAS=${KMS_KEY_ALIAS:-alias/ehr-cmk},S3_BUCKET=${S3_BUCKET:-ehr-records},DDB_LEDGER_TABLE=${DDB_LEDGER_TABLE:-AuditLedger},DDB_POLICY_TABLE=${DDB_POLICY_TABLE:-AccessPolicies},SECRET_NAME=${SECRET_NAME:-ehr/jwt-signing-key},LOG_GROUP=${LOG_GROUP:-/ehr/app}}" \
      >/dev/null
    echo "Created Lambda $NAME"
  fi
}

deploy "${LAMBDA_SMART_CONTRACT:-ehr-smart-contract}" lambdas/smart_contract
deploy "${LAMBDA_AUDIT_APPENDER:-ehr-audit-appender}" lambdas/audit_appender
