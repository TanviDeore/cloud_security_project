"""Centralized config + boto3 client factories. Every cloud call goes through here."""
import os
import boto3
from botocore.config import Config

ENDPOINT_URL = os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566")
REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

KMS_KEY_ALIAS = os.environ.get("KMS_KEY_ALIAS", "alias/ehr-cmk")
S3_BUCKET = os.environ.get("S3_BUCKET", "ehr-records")
DDB_LEDGER_TABLE = os.environ.get("DDB_LEDGER_TABLE", "AuditLedger")
DDB_POLICY_TABLE = os.environ.get("DDB_POLICY_TABLE", "AccessPolicies")
SECRET_NAME = os.environ.get("SECRET_NAME", "ehr/jwt-signing-key")
LAMBDA_SMART_CONTRACT = os.environ.get("LAMBDA_SMART_CONTRACT", "ehr-smart-contract")
LAMBDA_AUDIT_APPENDER = os.environ.get("LAMBDA_AUDIT_APPENDER", "ehr-audit-appender")
LOG_GROUP = os.environ.get("LOG_GROUP", "/ehr/app")
LOG_STREAM = os.environ.get("LOG_STREAM", "events")

_BOTO_CFG = Config(
    region_name=REGION,
    retries={"max_attempts": 3, "mode": "standard"},
    connect_timeout=5,
    read_timeout=15,
)


def _client(service: str):
    return boto3.client(
        service,
        endpoint_url=ENDPOINT_URL,
        region_name=REGION,
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
        config=_BOTO_CFG,
    )


def s3():
    return _client("s3")


def kms():
    return _client("kms")


def ddb():
    return _client("dynamodb")


def secrets():
    return _client("secretsmanager")


def cognito():
    return _client("cognito-idp")


def lambda_():
    return _client("lambda")


def logs():
    return _client("logs")


def cloudwatch():
    return _client("cloudwatch")
