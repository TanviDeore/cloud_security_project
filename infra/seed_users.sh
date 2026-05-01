#!/usr/bin/env bash
# Seeds initial users into the Users DynamoDB table:
#   - admin (random strong password, printed once)
#   - alice, bob (patients), dr_smith, dr_jones (doctors) for the demo
# Re-running keeps existing rows untouched (skips if username present).
#
# Bcrypt hashing is done in Python so the script doesn't depend on `htpasswd`.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")"/.. && pwd)"
USERS=${DDB_USERS_TABLE:-Users}

ADMIN_PW=$(python3 -c "import secrets; print(secrets.token_urlsafe(12))")

python3 - "$USERS" "$ADMIN_PW" <<'PY'
import os, sys, time, json
import boto3, bcrypt

users_table = sys.argv[1]
admin_pw = sys.argv[2]

ddb = boto3.client(
    "dynamodb",
    endpoint_url=os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566"),
    region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
)

def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt(rounds=10)).decode()

def upsert(user: dict, force: bool = False):
    # Skip if already present (don't clobber existing user state on re-bootstrap)
    if not force:
        existing = ddb.get_item(TableName=users_table,
                                Key={"username": {"S": user["username"]}})
        if "Item" in existing:
            print(f"  user {user['username']} already exists — skipping")
            return
    item = {k: {"S": str(v)} if isinstance(v, str) else
              ({"BOOL": v} if isinstance(v, bool) else
               {"N": str(v)}) for k, v in user.items()}
    ddb.put_item(TableName=users_table, Item=item)
    print(f"  seeded {user['username']} ({user['role']}, status={user['status']})")

now = int(time.time())

# Admin: pre-provisioned out-of-band, never via the app
upsert({
    "username": "admin",
    "email": "admin@ehr.local",
    "role": "admin",
    "status": "active",
    "password_hash": hash_pw(admin_pw),
    "created_at": now,
    "failed_attempts": 0,
    "locked_until": 0,
}, force=False)

# Demo users (only seeded if not present; preserve any password reset)
DEMO_PW = "Demo!123"  # used only by seeded fixtures; signups choose their own
demo_users = [
    {"username": "alice",    "email": "alice@example.com",
     "role": "patient", "status": "active",
     "first_name": "Alice", "last_name": "Carter"},
    {"username": "bob",      "email": "bob@example.com",
     "role": "patient", "status": "active",
     "first_name": "Bob",   "last_name": "Nguyen"},
    {"username": "dr_smith", "email": "smith@clinic.example",
     "role": "doctor",  "status": "active",
     "first_name": "Evelyn", "last_name": "Smith",
     "npi": "1407871717", "license_state": "TX", "npi_verified": True},
    {"username": "dr_jones", "email": "jones@clinic.example",
     "role": "doctor",  "status": "active",
     "first_name": "Marcus", "last_name": "Jones",
     "npi": "1659373234", "license_state": "NY", "npi_verified": True},
]
for u in demo_users:
    u["password_hash"] = hash_pw(DEMO_PW)
    u["created_at"] = now
    u["failed_attempts"] = 0
    u["locked_until"] = 0
    upsert(u)

print()
print("=" * 70)
print(f"  ADMIN PASSWORD (stored hashed; this plaintext shown ONLY now):")
print(f"      admin / {admin_pw}")
print(f"  Demo users were seeded with password: {DEMO_PW}")
print("=" * 70)
PY
