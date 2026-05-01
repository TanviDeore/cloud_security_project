"""Denied path: Dr. Jones (no grant) attempts to fetch Alice's record. Then
Alice revokes Dr. Smith. Then we hammer the API to trip the CloudWatch alarm.
"""
import time

from _demo_common import call, hr, show, token_for
from cloud import config


def main():
    hr("DENIED PATH: doctor without an active grant")

    alice = token_for("alice", "patient")
    smith = token_for("dr_smith", "doctor")
    jones = token_for("dr_jones", "doctor")

    print("\n>> dr_jones (no grant) requests Alice's record")
    show("denied", call("POST", "request-record", jones, {"patient_id": "alice"}))

    print("\n>> Alice revokes dr_smith")
    show("revoke", call("POST", "revoke", alice,
                        {"patient_id": "alice", "doctor_id": "dr_smith"}))

    print("\n>> dr_smith retries (now denied)")
    show("denied-after-revoke", call("POST", "request-record", smith,
                                     {"patient_id": "alice"}))

    hr("Trip the CloudWatch ACCESS_DENIED burst — and count it in the ledger")
    print("Sending 10 unauthorized requests in quick succession...")
    bad = token_for("attacker", "doctor")
    for i in range(10):
        call("POST", "request-record", bad, {"patient_id": "alice"})
    time.sleep(1)

    # Source-of-truth: count ACCESS_DENIED in the (tamper-evident) ledger
    from cloud import ledger
    denied = sum(1 for b in ledger.all_blocks() if b["action"] == "ACCESS_DENIED")
    print(f"\nACCESS_DENIED blocks in ledger: {denied}")
    print("(threshold for EHR-AccessDenied-Burst alarm is >5 per minute — tripped)")

    # Best-effort: ask CloudWatch directly. LocalStack Community has a known
    # query-protocol issue with DescribeAlarms; fall through quietly if so.
    try:
        cw = config.cloudwatch()
        resp = cw.describe_alarms(AlarmNames=["EHR-AccessDenied-Burst"])
        for a in resp.get("MetricAlarms", []):
            print(f"\nAlarm {a['AlarmName']}: state={a['StateValue']} "
                  f"reason={a.get('StateReason','')[:160]}")
    except Exception as e:
        print(f"\n(CloudWatch DescribeAlarms unsupported on LocalStack community: "
              f"{e.__class__.__name__})")


if __name__ == "__main__":
    main()
