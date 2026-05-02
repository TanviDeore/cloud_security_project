"""Manage access requests from doctors to patients."""
import os
import time
import uuid
from typing import Any, Dict, List
from decimal import Decimal
from boto3.dynamodb.conditions import Key
from . import config

def _clean(obj):
    if isinstance(obj, list):
        return [_clean(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, Decimal):
        return int(obj) if obj == int(obj) else float(obj)
    return obj

def _table():
    import boto3
    return boto3.resource(
        "dynamodb",
        endpoint_url=config.ENDPOINT_URL,
        region_name=config.REGION,
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
    ).Table(os.environ.get("DDB_REQUESTS_TABLE", "AccessRequests"))

def create(patient_id: str, doctor_id: str, scope: str, ttl_seconds: int) -> str:
    request_id = f"{int(time.time()):010d}-{uuid.uuid4().hex[:6]}"
    _table().put_item(Item={
        "patient_id": patient_id,
        "request_id": request_id,
        "doctor_id": doctor_id,
        "scope": scope,
        "ttl_seconds": ttl_seconds,
        "status": "PENDING",
        "created_at": int(time.time()),
    })
    return request_id

def list_for_patient(patient_id: str) -> List[Dict[str, Any]]:
    resp = _table().query(
        KeyConditionExpression=Key("patient_id").eq(patient_id),
        ScanIndexForward=False
    )
    return _clean(resp.get("Items", []))

def get(patient_id: str, request_id: str) -> Dict[str, Any]:
    resp = _table().get_item(Key={"patient_id": patient_id, "request_id": request_id})
    return _clean(resp.get("Item"))

def set_status(patient_id: str, request_id: str, status: str):
    _table().update_item(
        Key={"patient_id": patient_id, "request_id": request_id},
        UpdateExpression="SET #s = :t",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":t": status}
    )
