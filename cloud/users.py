"""Users table client. Replaces the seed-file user store with DynamoDB-backed
identity (status, role, bcrypt password, lockout counters, NPI metadata)."""
import os
import time
from typing import Any, Dict, List, Optional

from boto3.dynamodb.conditions import Attr

from . import config

LOCKOUT_THRESHOLD = 5
LOCKOUT_SECONDS = 15 * 60  # 15 minutes


def _table():
    import boto3
    return boto3.resource(
        "dynamodb",
        endpoint_url=config.ENDPOINT_URL,
        region_name=config.REGION,
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
    ).Table(os.environ.get("DDB_USERS_TABLE", "Users"))


def get(username: str) -> Optional[Dict[str, Any]]:
    resp = _table().get_item(Key={"username": username})
    return resp.get("Item")


def put(item: Dict[str, Any]) -> None:
    _table().put_item(Item=item)


def update_failed_attempt(username: str) -> Dict[str, Any]:
    """Increment failed_attempts; lock if threshold reached."""
    user = get(username) or {}
    failed = int(user.get("failed_attempts", 0)) + 1
    locked_until = int(user.get("locked_until", 0))
    if failed >= LOCKOUT_THRESHOLD:
        locked_until = int(time.time()) + LOCKOUT_SECONDS
    _table().update_item(
        Key={"username": username},
        UpdateExpression="SET failed_attempts = :f, locked_until = :l",
        ExpressionAttributeValues={":f": failed, ":l": locked_until},
    )
    return {"failed_attempts": failed, "locked_until": locked_until}


def reset_attempts(username: str) -> None:
    _table().update_item(
        Key={"username": username},
        UpdateExpression="SET failed_attempts = :f, locked_until = :l",
        ExpressionAttributeValues={":f": 0, ":l": 0},
    )


def is_locked(user: Dict[str, Any]) -> bool:
    return int(user.get("locked_until", 0)) > int(time.time())


def list_by_role(role: str) -> List[Dict[str, Any]]:
    resp = _table().scan(FilterExpression=Attr("role").eq(role))
    return resp.get("Items", [])


def list_by_status(status: str) -> List[Dict[str, Any]]:
    resp = _table().scan(FilterExpression=Attr("status").eq(status))
    return resp.get("Items", [])


def set_status(username: str, status: str) -> None:
    _table().update_item(
        Key={"username": username},
        UpdateExpression="SET #s = :s",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": status},
    )


def all_users() -> List[Dict[str, Any]]:
    resp = _table().scan()
    return resp.get("Items", [])
