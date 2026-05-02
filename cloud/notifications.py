"""Per-user notification inbox stored in DynamoDB."""
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
    ).Table(os.environ.get("DDB_NOTIFS_TABLE", "Notifications"))


def push(username: str, message: str, link: str = "", category: str = "info") -> None:
    if not username:
        return
    notif_id = f"{int(time.time()*1000):013d}-{uuid.uuid4().hex[:6]}"
    _table().put_item(Item={
        "username": username,
        "notif_id": notif_id,
        "message": message,
        "link": link,
        "category": category,
        "created_at": int(time.time()),
        "read": False,
    })


def list_for(username: str, limit: int = 50) -> List[Dict[str, Any]]:
    resp = _table().query(
        KeyConditionExpression=Key("username").eq(username),
        ScanIndexForward=False,
        Limit=limit,
    )
    return _clean(resp.get("Items", []))


def unread_count(username: str) -> int:
    items = list_for(username, limit=200)
    return sum(1 for n in items if not n.get("read"))


def mark_all_read(username: str) -> None:
    for n in list_for(username, limit=200):
        if n.get("read"):
            continue
        _table().update_item(
            Key={"username": username, "notif_id": n["notif_id"]},
            UpdateExpression="SET #r = :t",
            ExpressionAttributeNames={"#r": "read"},
            ExpressionAttributeValues={":t": True},
        )
