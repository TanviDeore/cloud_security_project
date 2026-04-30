"""Patient -> doctor access grants stored in DynamoDB."""
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from boto3.dynamodb.conditions import Key

from . import config


def _table():
    import boto3
    return boto3.resource(
        "dynamodb",
        endpoint_url=config.ENDPOINT_URL,
        region_name=config.REGION,
    ).Table(config.DDB_POLICY_TABLE)


def grant(patient_id: str, doctor_id: str, scope: str = "read",
          ttl_seconds: int = 86400) -> Dict[str, Any]:
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
