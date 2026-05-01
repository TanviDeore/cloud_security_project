#!/usr/bin/env bash
set -euo pipefail
SECRET=${SECRET_NAME:-ehr/jwt-signing-key}

# Generate a random 64-byte signing key (HS512)
KEY=$(python3 -c "import secrets,base64; print(base64.urlsafe_b64encode(secrets.token_bytes(64)).decode())")

if awslocal secretsmanager describe-secret --secret-id "$SECRET" >/dev/null 2>&1; then
  awslocal secretsmanager put-secret-value \
    --secret-id "$SECRET" --secret-string "{\"key\":\"$KEY\"}" >/dev/null
  echo "Rotated secret $SECRET"
else
  awslocal secretsmanager create-secret \
    --name "$SECRET" \
    --description "JWT signing key for EHR platform" \
    --secret-string "{\"key\":\"$KEY\"}" >/dev/null
  echo "Created secret $SECRET"
fi
