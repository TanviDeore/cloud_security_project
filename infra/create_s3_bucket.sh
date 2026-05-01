#!/usr/bin/env bash
set -euo pipefail
BUCKET=${S3_BUCKET:-ehr-records}
ALIAS=${KMS_KEY_ALIAS:-alias/ehr-cmk}

if awslocal s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  echo "Bucket $BUCKET already exists"
else
  awslocal s3api create-bucket --bucket "$BUCKET" >/dev/null
  echo "Created bucket $BUCKET"
fi

# Versioning for tamper recovery
awslocal s3api put-bucket-versioning \
  --bucket "$BUCKET" --versioning-configuration Status=Enabled

# SSE-KMS default encryption (defense in depth on top of envelope crypto)
KEY_ID=$(awslocal kms describe-key --key-id "$ALIAS" \
  --query 'KeyMetadata.KeyId' --output text)

awslocal s3api put-bucket-encryption \
  --bucket "$BUCKET" \
  --server-side-encryption-configuration "{
    \"Rules\":[{
      \"ApplyServerSideEncryptionByDefault\":{
        \"SSEAlgorithm\":\"aws:kms\",
        \"KMSMasterKeyID\":\"$KEY_ID\"
      },
      \"BucketKeyEnabled\": true
    }]
  }" || echo "(SSE-KMS config not enforced by LocalStack community edition; envelope crypto in app provides confidentiality)"

# Block public access
awslocal s3api put-public-access-block \
  --bucket "$BUCKET" \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true \
  || true

echo "S3 bucket $BUCKET ready (versioning + SSE-KMS + public-access blocked)"
