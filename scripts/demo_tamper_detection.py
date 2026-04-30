"""Tamper demo: surgically edit a DynamoDB block and watch verify_chain fail.

This is the most visually striking part of the recording. We pick the middle
block, change its 'actor' field in place (without recomputing the hash), then
re-run verify_chain — it reports the exact block_id where the chain broke.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cloud import config, ledger
from _demo_common import call, hr, show, token_for


def main():
    hr("TAMPER DEMO: edit a block in place, then verify_chain")

    smith = token_for("dr_smith", "doctor")
    pre = call("GET", "verify-chain", smith)
    show("verify before tamper", pre)

    blocks = list(ledger.all_blocks())
    if len(blocks) < 2:
        print("\n[!] Need at least 2 blocks. Run demo_happy_path.py first.")
        return

    target = blocks[len(blocks) // 2]
    print(f"\n>> Tampering with block #{int(target['block_id'])} "
          f"(was actor={target['actor']!r})")

    config.ddb().update_item(
        TableName=config.DDB_LEDGER_TABLE,
        Key={"chain": {"S": "ehr"},
             "block_id": {"N": str(int(target["block_id"]))}},
        UpdateExpression="SET actor = :a",
        ExpressionAttributeValues={":a": {"S": "EVIL_INSIDER"}},
    )
    print("   block edited in place (hash NOT recomputed)")

    post = call("GET", "verify-chain", smith)
    show("verify after tamper", post)

    print("\n>> Restoring original actor so subsequent demos still pass")
    config.ddb().update_item(
        TableName=config.DDB_LEDGER_TABLE,
        Key={"chain": {"S": "ehr"},
             "block_id": {"N": str(int(target["block_id"]))}},
        UpdateExpression="SET actor = :a",
        ExpressionAttributeValues={":a": {"S": target["actor"]}},
    )
    final = call("GET", "verify-chain", smith)
    show("verify after restore", final)


if __name__ == "__main__":
    main()
