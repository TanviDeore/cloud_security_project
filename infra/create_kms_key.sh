#!/usr/bin/env bash
set -euo pipefail
ALIAS=${KMS_KEY_ALIAS:-alias/ehr-cmk}

EXISTING=$(awslocal kms list-aliases \
  --query "Aliases[?AliasName=='${ALIAS}'].TargetKeyId" --output text || true)

if [ -n "$EXISTING" ] && [ "$EXISTING" != "None" ]; then
  echo "KMS alias ${ALIAS} already exists (key=${EXISTING})"
  exit 0
fi

KEY_ID=$(awslocal kms create-key \
  --description "EHR customer master key" \
  --key-usage ENCRYPT_DECRYPT \
  --query 'KeyMetadata.KeyId' --output text)

awslocal kms create-alias \
  --alias-name "$ALIAS" --target-key-id "$KEY_ID"

awslocal kms enable-key-rotation --key-id "$KEY_ID" || true
echo "Created KMS key $KEY_ID with alias $ALIAS"
