#!/usr/bin/env bash
set -euo pipefail
LEDGER=${DDB_LEDGER_TABLE:-AuditLedger}
POLICY=${DDB_POLICY_TABLE:-AccessPolicies}

create_table() {
  local NAME=$1; local KEY_SCHEMA=$2; local ATTR_DEFS=$3
  if aws --endpoint-url "$AWS_ENDPOINT_URL" dynamodb describe-table --table-name "$NAME" >/dev/null 2>&1; then
    echo "Table $NAME already exists"
    return
  fi
  aws --endpoint-url "$AWS_ENDPOINT_URL" dynamodb create-table \
    --table-name "$NAME" \
    --key-schema $KEY_SCHEMA \
    --attribute-definitions $ATTR_DEFS \
    --billing-mode PAY_PER_REQUEST >/dev/null
  echo "Created table $NAME"
}

# Ledger: partition by 'chain' (single chain), sort by numeric block_id
create_table "$LEDGER" \
  "AttributeName=chain,KeyType=HASH AttributeName=block_id,KeyType=RANGE" \
  "AttributeName=chain,AttributeType=S AttributeName=block_id,AttributeType=N"

# Policy: partition by patient_id, sort by doctor_id
create_table "$POLICY" \
  "AttributeName=patient_id,KeyType=HASH AttributeName=doctor_id,KeyType=RANGE" \
  "AttributeName=patient_id,AttributeType=S AttributeName=doctor_id,AttributeType=S"
