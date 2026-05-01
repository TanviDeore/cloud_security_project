"""Tamper-evident audit ledger on DynamoDB.

Each block:
  chain      : "ehr"             (single chain partition)
  block_id   : monotonically increasing integer
  timestamp  : ISO-8601 UTC
  actor      : username (sub from JWT)
  action     : ACCESS_GRANTED | ACCESS_DENIED | RECORD_FETCH | GRANT | REVOKE
  resource   : patient_id
  details    : JSON string with extra context
  prev_hash  : hex SHA-256 of previous block (or "GENESIS")
  hash       : hex SHA-256 over (block_id|timestamp|actor|action|resource|details|prev_hash)

verify_chain() walks the ledger in order and returns the first block_id whose
hash or prev_hash linkage is broken; returns None if intact.
"""
import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, Optional

from boto3.dynamodb.conditions import Key

from . import config

CHAIN = "ehr"
GENESIS_HASH = "GENESIS"


def _hash(block: Dict[str, Any]) -> str:
    payload = "|".join([
        str(block["block_id"]),
        block["timestamp"],
        block["actor"],
        block["action"],
        block["resource"],
        block["details"],
        block["prev_hash"],
    ])
    return hashlib.sha256(payload.encode()).hexdigest()


def _table():
    import os
    import boto3
    return boto3.resource(
        "dynamodb",
        endpoint_url=config.ENDPOINT_URL,
        region_name=config.REGION,
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
    ).Table(config.DDB_LEDGER_TABLE)


def _last_block() -> Optional[Dict[str, Any]]:
    resp = _table().query(
        KeyConditionExpression=Key("chain").eq(CHAIN),
        ScanIndexForward=False,
        Limit=1,
    )
    items = resp.get("Items", [])
    return items[0] if items else None


def append_block(actor: str, action: str, resource: str, details: Dict[str, Any]) -> Dict[str, Any]:
    last = _last_block()
    block_id = int(last["block_id"]) + 1 if last else 1
    prev_hash = last["hash"] if last else GENESIS_HASH
    block = {
        "chain": CHAIN,
        "block_id": block_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "action": action,
        "resource": resource,
        "details": json.dumps(details, separators=(",", ":")),
        "prev_hash": prev_hash,
    }
    block["hash"] = _hash(block)
    _table().put_item(Item=block)
    return block


def all_blocks() -> Iterator[Dict[str, Any]]:
    last_eval = None
    while True:
        kwargs = {
            "KeyConditionExpression": Key("chain").eq(CHAIN),
            "ScanIndexForward": True,
        }
        if last_eval:
            kwargs["ExclusiveStartKey"] = last_eval
        resp = _table().query(**kwargs)
        for item in resp.get("Items", []):
            yield item
        last_eval = resp.get("LastEvaluatedKey")
        if not last_eval:
            return


def verify_chain() -> Dict[str, Any]:
    """Returns {valid: bool, broken_at: int|None, total: int}."""
    expected_prev = GENESIS_HASH
    expected_id = 1
    total = 0
    for block in all_blocks():
        total += 1
        if int(block["block_id"]) != expected_id:
            return {"valid": False, "broken_at": int(block["block_id"]),
                    "reason": "non-sequential block_id", "total": total}
        if block["prev_hash"] != expected_prev:
            return {"valid": False, "broken_at": int(block["block_id"]),
                    "reason": "prev_hash mismatch", "total": total}
        recomputed = _hash({
            "block_id": int(block["block_id"]),
            "timestamp": block["timestamp"],
            "actor": block["actor"],
            "action": block["action"],
            "resource": block["resource"],
            "details": block["details"],
            "prev_hash": block["prev_hash"],
        })
        if recomputed != block["hash"]:
            return {"valid": False, "broken_at": int(block["block_id"]),
                    "reason": "hash mismatch (block was edited)", "total": total}
        expected_prev = block["hash"]
        expected_id += 1
    return {"valid": True, "broken_at": None, "total": total}
