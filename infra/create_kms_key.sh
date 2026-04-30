#!/usr/bin/env bash
set -euo pipefail
ALIAS=${KMS_KEY_ALIAS:-alias/ehr-cmk}

EXISTING=$(aws --endpoint-url "$AWS_ENDPOINT_URL" kms list-aliases \
  --query "Aliases[?AliasName=='${ALIAS}'].TargetKeyId" --output text || true)

if [ -n "$EXISTING" ] && [ "$EXISTING" != "None" ]; then
  echo "KMS alias ${ALIAS} already exists (key=${EXISTING})"
  exit 0
fi

KEY_ID=$(aws --endpoint-url "$AWS_ENDPOINT_URL" kms create-key \
  --description "EHR customer master key" \
  --key-usage ENCRYPT_DECRYPT \
  --query 'KeyMetadata.KeyId' --output text)

aws --endpoint-url "$AWS_ENDPOINT_URL" kms create-alias \
  --alias-name "$ALIAS" --target-key-id "$KEY_ID"

aws --endpoint-url "$AWS_ENDPOINT_URL" kms enable-key-rotation --key-id "$KEY_ID" || true
echo "Created KMS key $KEY_ID with alias $ALIAS"
