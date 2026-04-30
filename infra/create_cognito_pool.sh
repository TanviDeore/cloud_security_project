#!/usr/bin/env bash
set -euo pipefail
POOL_NAME=${COGNITO_POOL_NAME:-ehr-users}

EXISTING=$(aws --endpoint-url "$AWS_ENDPOINT_URL" cognito-idp list-user-pools \
  --max-results 50 --query "UserPools[?Name=='${POOL_NAME}'].Id" --output text || true)

if [ -n "$EXISTING" ] && [ "$EXISTING" != "None" ]; then
  POOL_ID="$EXISTING"
  echo "Cognito pool $POOL_NAME exists ($POOL_ID)"
else
  POOL_ID=$(aws --endpoint-url "$AWS_ENDPOINT_URL" cognito-idp create-user-pool \
    --pool-name "$POOL_NAME" \
    --policies "PasswordPolicy={MinimumLength=8,RequireUppercase=false,RequireLowercase=false,RequireNumbers=false,RequireSymbols=false}" \
    --schema "Name=role,AttributeDataType=String,Mutable=true,Required=false" \
    --query 'UserPool.Id' --output text)
  echo "Created Cognito pool $POOL_NAME ($POOL_ID)"
fi

# App client
CLIENT_ID=$(aws --endpoint-url "$AWS_ENDPOINT_URL" cognito-idp list-user-pool-clients \
  --user-pool-id "$POOL_ID" --query 'UserPoolClients[0].ClientId' --output text 2>/dev/null || true)
if [ -z "$CLIENT_ID" ] || [ "$CLIENT_ID" = "None" ]; then
  CLIENT_ID=$(aws --endpoint-url "$AWS_ENDPOINT_URL" cognito-idp create-user-pool-client \
    --user-pool-id "$POOL_ID" \
    --client-name "ehr-flask" \
    --explicit-auth-flows ADMIN_NO_SRP_AUTH \
    --query 'UserPoolClient.ClientId' --output text)
  echo "Created Cognito client $CLIENT_ID"
fi

mkdir -p ../.localstack
echo "{\"pool_id\":\"$POOL_ID\",\"client_id\":\"$CLIENT_ID\"}" > ../.localstack/cognito.json
echo "Wrote .localstack/cognito.json"

# Seed users (idempotent: ignore errors on re-run)
seed_user() {
  local USERNAME=$1; local ROLE=$2; local PASS=$3
  aws --endpoint-url "$AWS_ENDPOINT_URL" cognito-idp admin-create-user \
    --user-pool-id "$POOL_ID" --username "$USERNAME" \
    --user-attributes Name=custom:role,Value="$ROLE" \
    --message-action SUPPRESS >/dev/null 2>&1 || true
  aws --endpoint-url "$AWS_ENDPOINT_URL" cognito-idp admin-set-user-password \
    --user-pool-id "$POOL_ID" --username "$USERNAME" \
    --password "$PASS" --permanent >/dev/null 2>&1 || true
  echo "Seeded $USERNAME ($ROLE)"
}

seed_user alice    patient password
seed_user bob      patient password
seed_user dr_smith doctor  password
seed_user dr_jones doctor  password
