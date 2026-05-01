#!/usr/bin/env bash
# AuthN seed.
#
# In production this script provisions an Amazon Cognito user pool. LocalStack
# Community Edition (used for this demo) does not implement cognito-idp, so we
# fall back to a local seed file. The Flask login flow tries Cognito first and
# uses this file only when Cognito is unavailable. Either way, the cloud
# design intent — managed identity service — is preserved.
set -euo pipefail

POOL_NAME=${COGNITO_POOL_NAME:-ehr-users}

ROOT="$(cd "$(dirname "$0")"/.. && pwd)"
mkdir -p "$ROOT/.localstack"

cognito_supported() {
  awslocal cognito-idp list-user-pools --max-results 1 >/dev/null 2>&1
}

if cognito_supported; then
  EXISTING=$(awslocal cognito-idp list-user-pools \
    --max-results 50 --query "UserPools[?Name=='${POOL_NAME}'].Id" --output text || true)
  if [ -n "$EXISTING" ] && [ "$EXISTING" != "None" ]; then
    POOL_ID="$EXISTING"
  else
    POOL_ID=$(awslocal cognito-idp create-user-pool \
      --pool-name "$POOL_NAME" \
      --query 'UserPool.Id' --output text)
  fi
  CLIENT_ID=$(awslocal cognito-idp list-user-pool-clients \
    --user-pool-id "$POOL_ID" --query 'UserPoolClients[0].ClientId' --output text 2>/dev/null || true)
  if [ -z "$CLIENT_ID" ] || [ "$CLIENT_ID" = "None" ]; then
    CLIENT_ID=$(awslocal cognito-idp create-user-pool-client \
      --user-pool-id "$POOL_ID" --client-name "ehr-flask" \
      --explicit-auth-flows ADMIN_NO_SRP_AUTH \
      --query 'UserPoolClient.ClientId' --output text)
  fi
  echo "{\"backend\":\"cognito\",\"pool_id\":\"$POOL_ID\",\"client_id\":\"$CLIENT_ID\"}" \
    > "$ROOT/.localstack/cognito.json"
  echo "Cognito pool ready ($POOL_ID)"
else
  echo "(LocalStack Community has no cognito-idp; seeding local user file instead)"
fi

cat > "$ROOT/.localstack/users.json" <<'JSON'
{
  "backend": "local",
  "users": [
    {"username": "alice",    "password": "password", "role": "patient"},
    {"username": "bob",      "password": "password", "role": "patient"},
    {"username": "dr_smith", "password": "password", "role": "doctor"},
    {"username": "dr_jones", "password": "password", "role": "doctor"}
  ]
}
JSON
echo "Wrote .localstack/users.json (alice, bob, dr_smith, dr_jones / password)"
