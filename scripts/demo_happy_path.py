"""Happy path: Alice grants Dr. Smith -> Dr. Smith fetches -> ledger entries."""
from _demo_common import call, hr, show, token_for


def main():
    hr("HAPPY PATH: Alice grants Dr. Smith, then Dr. Smith fetches her record")

    alice = token_for("alice", "patient")
    smith = token_for("dr_smith", "doctor")

    print("\n>> Alice grants 24h read access to dr_smith")
    show("grant", call("POST", "grant", alice,
                       {"patient_id": "alice", "doctor_id": "dr_smith",
                        "scope": "read", "ttl_seconds": 86400}))

    print("\n>> dr_smith requests Alice's record (should succeed)")
    show("request-record", call("POST", "request-record", smith,
                                 {"patient_id": "alice"}))

    print("\n>> Verify chain integrity")
    show("verify-chain", call("GET", "verify-chain", smith))

    print("\n>> Audit trail (all blocks)")
    show("audit", call("GET", "audit", smith))


if __name__ == "__main__":
    main()
