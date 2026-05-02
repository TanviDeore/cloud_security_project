import os
import sys
import time
import boto3
import bcrypt

# Configuration for LocalStack
AWS_ENDPOINT_URL = os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566")
REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

ddb = boto3.client(
    "dynamodb",
    endpoint_url=AWS_ENDPOINT_URL,
    region_name=REGION,
    aws_access_key_id="test",
    aws_secret_access_key="test",
)

def create_table(name, key_schema, attr_defs):
    try:
        ddb.describe_table(TableName=name)
        print(f"Table {name} already exists")
    except ddb.exceptions.ResourceNotFoundException:
        ddb.create_table(
            TableName=name,
            KeySchema=key_schema,
            AttributeDefinitions=attr_defs,
            BillingMode="PAY_PER_REQUEST"
        )
        print(f"Created table {name}")

def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt(rounds=10)).decode()

def seed_users():
    users_table = "Users"
    now = int(time.time())
    demo_pw = "Demo!123"
    
    users = [
        {"username": "admin", "email": "admin@ehr.local", "role": "admin", "status": "active", "password": "admin"},
        {"username": "alice", "email": "alice@example.com", "role": "patient", "status": "active", "first_name": "Alice", "last_name": "Carter", "password": demo_pw},
        {"username": "bob", "email": "bob@example.com", "role": "patient", "status": "active", "first_name": "Bob", "last_name": "Nguyen", "password": demo_pw},
        {"username": "dr_smith", "email": "smith@clinic.example", "role": "doctor", "status": "active", "first_name": "Evelyn", "last_name": "Smith", "npi": "1407871717", "license_state": "TX", "npi_verified": True, "password": demo_pw},
        {"username": "dr_jones", "email": "jones@clinic.example", "role": "doctor", "status": "active", "first_name": "Marcus", "last_name": "Jones", "npi": "1659373234", "license_state": "NY", "npi_verified": True, "password": demo_pw},
    ]
    
    for u in users:
        try:
            existing = ddb.get_item(TableName=users_table, Key={"username": {"S": u["username"]}})
            if "Item" in existing:
                print(f"User {u['username']} already exists")
                continue
        except Exception:
            pass
            
        password = u.pop("password")
        item = {k: {"S": str(v)} if isinstance(v, str) else ({"BOOL": v} if isinstance(v, bool) else {"N": str(v)}) for k, v in u.items()}
        item["password_hash"] = {"S": hash_pw(password)}
        item["created_at"] = {"N": str(now)}
        item["failed_attempts"] = {"N": "0"}
        item["locked_until"] = {"N": "0"}
        
        ddb.put_item(TableName=users_table, Item=item)
        print(f"Seeded {u['username']}")

if __name__ == "__main__":
    # Create Tables
    create_table("AuditLedger", 
                 [{"AttributeName": "chain", "KeyType": "HASH"}, {"AttributeName": "block_id", "KeyType": "RANGE"}],
                 [{"AttributeName": "chain", "AttributeType": "S"}, {"AttributeName": "block_id", "AttributeType": "N"}])
    
    create_table("AccessPolicies",
                 [{"AttributeName": "patient_id", "KeyType": "HASH"}, {"AttributeName": "doctor_id", "KeyType": "RANGE"}],
                 [{"AttributeName": "patient_id", "AttributeType": "S"}, {"AttributeName": "doctor_id", "AttributeType": "S"}])
                 
    create_table("Users",
                 [{"AttributeName": "username", "KeyType": "HASH"}],
                 [{"AttributeName": "username", "AttributeType": "S"}])
                 
    create_table("Notifications",
                 [{"AttributeName": "username", "KeyType": "HASH"}, {"AttributeName": "notif_id", "KeyType": "RANGE"}],
                 [{"AttributeName": "username", "AttributeType": "S"}, {"AttributeName": "notif_id", "AttributeType": "S"}])
    
    create_table("AccessRequests",
                 [{"AttributeName": "patient_id", "KeyType": "HASH"}, {"AttributeName": "request_id", "KeyType": "RANGE"}],
                 [{"AttributeName": "patient_id", "AttributeType": "S"}, {"AttributeName": "request_id", "AttributeType": "S"}])
    
    # Seed Users
    seed_users()
    print("Bootstrap complete")
