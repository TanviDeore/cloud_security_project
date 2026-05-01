"""Patient -> doctor access grants stored in DynamoDB.

Scopes (least-privilege ladder):
    read    — view current record
    write   — read + append clinical notes (creates new S3 version)
    history — write + view full version history
"""
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from boto3.dynamodb.conditions import Key

from . import config

VALID_SCOPES = ("read", "write", "history")
SCOPE_RANK = {"read": 1, "write": 2, "history": 3}


def scope_includes(grant_scope: str, required: str) -> bool:
    return SCOPE_RANK.get(grant_scope, 0) >= SCOPE_RANK.get(required, 99)


def _table():
    import boto3
    return boto3.resource(
        "dynamodb",
        endpoint_url=config.ENDPOINT_URL,
        region_name=config.REGION,
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
    ).Table(config.DDB_POLICY_TABLE)


def grant(patient_id: str, doctor_id: str, scope: str = "read",
          ttl_seconds: int = 86400) -> Dict[str, Any]:
    if scope not in VALID_SCOPES:
        scope = "read"
    expires_at = int(time.time()) + ttl_seconds
    item = {
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "scope": scope,
        "expires_at": expires_at,
        "granted_at": datetime.now(timezone.utc).isoformat(),
        "revoked": False,
    }
    _table().put_item(Item=item)
    return item


def revoke(patient_id: str, doctor_id: str) -> None:
    _table().update_item(
        Key={"patient_id": patient_id, "doctor_id": doctor_id},
        UpdateExpression="SET revoked = :r, expires_at = :e",
        ExpressionAttributeValues={":r": True, ":e": 0},
    )


def lookup(patient_id: str, doctor_id: str) -> Optional[Dict[str, Any]]:
    resp = _table().get_item(Key={"patient_id": patient_id, "doctor_id": doctor_id})
    item = resp.get("Item")
    if not item:
        return None
    if item.get("revoked") or int(item.get("expires_at", 0)) < int(time.time()):
        return None
    return item


def list_grants(patient_id: str) -> List[Dict[str, Any]]:
    resp = _table().query(KeyConditionExpression=Key("patient_id").eq(patient_id))
    return resp.get("Items", [])


def list_grants_for_doctor(doctor_id: str) -> List[Dict[str, Any]]:
    """Active grants visible to a particular doctor (across all patients)."""
    from boto3.dynamodb.conditions import Attr
    resp = _table().scan(FilterExpression=Attr("doctor_id").eq(doctor_id))
    now = int(time.time())
    return [g for g in resp.get("Items", [])
            if not g.get("revoked") and int(g.get("expires_at", 0)) >= now]
