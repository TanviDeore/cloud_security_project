"""End-to-end via the Lambda (direct invoke). Requires bootstrap to have run."""
import pytest

from app.api_gateway_client import call
from cloud import policy_store, s3_store
from scripts._demo_common import token_for


@pytest.fixture(autouse=True)
def _seed():
    s3_store.put_record("alice", {"patient_id": "alice", "note": "fixture"})
    s3_store.put_record("bob", {"patient_id": "bob", "note": "fixture"})
    yield
    try:
        policy_store.revoke("alice", "dr_smith")
    except Exception:
        pass


def test_doctor_without_grant_denied():
    smith = token_for("dr_smith", "doctor")
    r = call("POST", "request-record", smith, {"patient_id": "alice"})
    assert r["status"] == 403


def test_doctor_with_grant_succeeds():
    alice = token_for("alice", "patient")
    smith = token_for("dr_smith", "doctor")
    g = call("POST", "grant", alice,
             {"patient_id": "alice", "doctor_id": "dr_smith",
              "scope": "read", "ttl_seconds": 600})
    assert g["status"] == 200
    r = call("POST", "request-record", smith, {"patient_id": "alice"})
    assert r["status"] == 200
    assert r["body"]["record"]["patient_id"] == "alice"


def test_patient_cannot_grant_on_other():
    alice = token_for("alice", "patient")
    r = call("POST", "grant", alice,
             {"patient_id": "bob", "doctor_id": "dr_smith"})
    assert r["status"] == 403


def test_revoke_blocks_subsequent_request():
    alice = token_for("alice", "patient")
    smith = token_for("dr_smith", "doctor")
    call("POST", "grant", alice,
         {"patient_id": "alice", "doctor_id": "dr_smith", "ttl_seconds": 600})
    call("POST", "revoke", alice,
         {"patient_id": "alice", "doctor_id": "dr_smith"})
    r = call("POST", "request-record", smith, {"patient_id": "alice"})
    assert r["status"] == 403
