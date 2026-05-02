import os
import boto3

# Configuration for LocalStack
AWS_ENDPOINT_URL = os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566")
REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
ALIAS = os.environ.get("KMS_SIGNER_ALIAS", "alias/ehr-pdf-signer")

kms_client = boto3.client(
    "kms",
    endpoint_url=AWS_ENDPOINT_URL,
    region_name=REGION,
    aws_access_key_id="test",
    aws_secret_access_key="test",
)

def create_signer_key():
    try:
        aliases = kms_client.list_aliases()["Aliases"]
        existing = [a for a in aliases if a["AliasName"] == ALIAS]
        if existing:
            print(f"Signer alias {ALIAS} already exists")
            return
    except Exception as e:
        print(f"Error listing aliases: {e}")

    try:
        response = kms_client.create_key(
            Description="EHR PDF signing key (asymmetric RSA)",
            KeyUsage="SIGN_VERIFY",
            CustomerMasterKeySpec="RSA_2048"
        )
        key_id = response["KeyMetadata"]["KeyId"]
        kms_client.create_alias(
            AliasName=ALIAS,
            TargetKeyId=key_id
        )
        print(f"Created signer key {key_id} with alias {ALIAS}")
    except Exception as e:
        print(f"Error creating key: {e}")

if __name__ == "__main__":
    create_signer_key()
