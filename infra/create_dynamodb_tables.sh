#!/usr/bin/env bash
set -euo pipefail
LEDGER=${DDB_LEDGER_TABLE:-AuditLedger}
POLICY=${DDB_POLICY_TABLE:-AccessPolicies}
USERS=${DDB_USERS_TABLE:-Users}
NOTIFS=${DDB_NOTIFS_TABLE:-Notifications}

create_table() {
  local NAME=$1; local KEY_SCHEMA=$2; local ATTR_DEFS=$3
  if awslocal dynamodb describe-table --table-name "$NAME" >/dev/null 2>&1; then
    echo "Table $NAME already exists"
    return
  fi
  awslocal dynamodb create-table \
    --table-name "$NAME" \
    --key-schema $KEY_SCHEMA \
    --attribute-definitions $ATTR_DEFS \
    --billing-mode PAY_PER_REQUEST >/dev/null
  echo "Created table $NAME"
}

# Audit ledger: single chain partition, sort by numeric block_id
create_table "$LEDGER" \
  "AttributeName=chain,KeyType=HASH AttributeName=block_id,KeyType=RANGE" \
  "AttributeName=chain,AttributeType=S AttributeName=block_id,AttributeType=N"

# Patient -> doctor grants
create_table "$POLICY" \
  "AttributeName=patient_id,KeyType=HASH AttributeName=doctor_id,KeyType=RANGE" \
  "AttributeName=patient_id,AttributeType=S AttributeName=doctor_id,AttributeType=S"

# Users: identity + bcrypt password hash + lockout state
create_table "$USERS" \
  "AttributeName=username,KeyType=HASH" \
  "AttributeName=username,AttributeType=S"

# Notifications: per-user inbox
create_table "$NOTIFS" \
  "AttributeName=username,KeyType=HASH AttributeName=notif_id,KeyType=RANGE" \
  "AttributeName=username,AttributeType=S AttributeName=notif_id,AttributeType=S"
