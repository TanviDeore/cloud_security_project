#!/usr/bin/env bash
# Asymmetric KMS key used to sign patient-export PDFs (audit log proofs).
# Separate from the symmetric CMK used for envelope encryption.
set -euo pipefail
ALIAS=${KMS_SIGNER_ALIAS:-alias/ehr-pdf-signer}

EXISTING=$(awslocal kms list-aliases \
  --query "Aliases[?AliasName=='${ALIAS}'].TargetKeyId" --output text || true)

if [ -n "$EXISTING" ] && [ "$EXISTING" != "None" ]; then
  echo "Signer alias ${ALIAS} already exists (key=${EXISTING})"
  exit 0
fi

KEY_ID=$(awslocal kms create-key \
  --description "EHR PDF signing key (asymmetric RSA)" \
  --key-usage SIGN_VERIFY \
  --customer-master-key-spec RSA_2048 \
  --query 'KeyMetadata.KeyId' --output text)

awslocal kms create-alias --alias-name "$ALIAS" --target-key-id "$KEY_ID"
echo "Created signer key $KEY_ID with alias $ALIAS"
