"""Audit-appender Lambda. Invoked async by other components that want to add
an arbitrary block without going through the smart contract (e.g. system
events, scheduled key-rotation logs).
"""
import json
from cloud import ledger


def lambda_handler(event, context):
    body = event if isinstance(event, dict) else json.loads(event)
    actor = body.get("actor", "system")
    action = body.get("action", "SYSTEM_EVENT")
    resource = body.get("resource", "system::*")
    details = body.get("details", {})
    blk = ledger.append_block(actor, action, resource, details)
    return {"block_id": blk["block_id"], "hash": blk["hash"]}
