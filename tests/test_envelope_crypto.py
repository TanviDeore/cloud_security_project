"""Round-trip envelope encryption against live KMS + S3."""
import pytest

from cloud import s3_store


def test_put_then_get_roundtrip():
    record = {"patient_id": "test_alice", "blood_type": "O+",
              "conditions": [{"name": "test", "status": "ok"}]}
    s3_store.put_record("test_alice", record)
    fetched = s3_store.get_record("test_alice")
    assert fetched == record


def test_record_exists():
    s3_store.put_record("test_bob", {"patient_id": "test_bob"})
    assert s3_store.record_exists("test_bob") is True
    assert s3_store.record_exists("nobody_xyz") is False
