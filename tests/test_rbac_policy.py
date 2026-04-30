"""IAM-style policy evaluator unit tests (no cloud calls)."""
from lambdas.smart_contract.rbac_policy import evaluate


def test_patient_can_grant_on_self():
    ok, _ = evaluate({"username": "alice", "role": "patient"},
                     "grant", "patient::alice", {})
    assert ok


def test_patient_cannot_grant_on_other():
    ok, _ = evaluate({"username": "alice", "role": "patient"},
                     "grant", "patient::bob", {})
    assert not ok


def test_doctor_request_requires_grant():
    p = {"username": "dr_smith", "role": "doctor"}
    ok_no_grant, _ = evaluate(p, "request-record", "patient::alice",
                              {"GrantExists": False})
    ok_with_grant, _ = evaluate(p, "request-record", "patient::alice",
                                {"GrantExists": True})
    assert not ok_no_grant
    assert ok_with_grant


def test_unknown_role_denied():
    ok, _ = evaluate({"username": "x", "role": "intruder"},
                     "request-record", "patient::alice", {"GrantExists": True})
    assert not ok
