"""Chain integrity tests against the live DynamoDB ledger."""
import pytest

from cloud import config, ledger


def test_append_block_links_to_previous():
    a = ledger.append_block("alice", "TEST", "patient::alice", {"i": 1})
    b = ledger.append_block("alice", "TEST", "patient::alice", {"i": 2})
    assert b["prev_hash"] == a["hash"]
    assert int(b["block_id"]) == int(a["block_id"]) + 1


def test_verify_chain_intact():
    ledger.append_block("alice", "TEST", "patient::alice", {"i": 99})
    result = ledger.verify_chain()
    assert result["valid"] is True
    assert result["broken_at"] is None


def test_tampering_breaks_verification():
    blk = ledger.append_block("alice", "TEST", "patient::alice", {"i": 100})
    config.ddb().update_item(
        TableName=config.DDB_LEDGER_TABLE,
        Key={"chain": {"S": "ehr"},
             "block_id": {"N": str(int(blk["block_id"]))}},
        UpdateExpression="SET actor = :a",
        ExpressionAttributeValues={":a": {"S": "EVIL"}},
    )
    result = ledger.verify_chain()
    assert result["valid"] is False
    assert result["broken_at"] == int(blk["block_id"])

    # Restore so later tests aren't poisoned
    config.ddb().update_item(
        TableName=config.DDB_LEDGER_TABLE,
        Key={"chain": {"S": "ehr"},
             "block_id": {"N": str(int(blk["block_id"]))}},
        UpdateExpression="SET actor = :a",
        ExpressionAttributeValues={":a": {"S": blk["actor"]}},
    )
    assert ledger.verify_chain()["valid"] is True
