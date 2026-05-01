"""EHR storage on S3 with KMS envelope encryption + versioning.

Object layout:
  Key:      patients/{patient_id}.ehr
  Body:     12-byte nonce || GCM ciphertext || 16-byte tag
  Metadata: x-amz-meta-edk = base64(encrypted-data-key)
            x-amz-meta-alg = AES-256-GCM

Bucket has versioning enabled and SSE-KMS as defense in depth. Each call to
put_record() returns the S3 versionId, which the smart-contract Lambda
records in the audit ledger so a clinical note can be tied back to the
specific record version that produced it.
"""
import base64
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from Crypto.Cipher import AES

from . import config, kms_client

NONCE_BYTES = 12


def _key(patient_id: str) -> str:
    return f"patients/{patient_id}.ehr"


def put_record(patient_id: str, record: Dict[str, Any]) -> Dict[str, Any]:
    plaintext = json.dumps(record, separators=(",", ":")).encode()
    data_key, edk = kms_client.generate_data_key()
    nonce = os.urandom(NONCE_BYTES)
    cipher = AES.new(data_key, AES.MODE_GCM, nonce=nonce)
    ct, tag = cipher.encrypt_and_digest(plaintext)
    body = nonce + ct + tag
    resp = config.s3().put_object(
        Bucket=config.S3_BUCKET,
        Key=_key(patient_id),
        Body=body,
        Metadata={
            "edk": base64.b64encode(edk).decode(),
            "alg": "AES-256-GCM",
        },
        ContentType="application/octet-stream",
    )
    return {"version_id": resp.get("VersionId", "null"),
            "etag": resp.get("ETag", "").strip('"')}


def get_record(patient_id: str, version_id: Optional[str] = None) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {"Bucket": config.S3_BUCKET, "Key": _key(patient_id)}
    if version_id:
        kwargs["VersionId"] = version_id
    obj = config.s3().get_object(**kwargs)
    body = obj["Body"].read()
    edk = base64.b64decode(obj["Metadata"]["edk"])
    data_key = kms_client.decrypt_data_key(edk)
    nonce, ct, tag = body[:NONCE_BYTES], body[NONCE_BYTES:-16], body[-16:]
    cipher = AES.new(data_key, AES.MODE_GCM, nonce=nonce)
    plaintext = cipher.decrypt_and_verify(ct, tag)
    return json.loads(plaintext)


def record_exists(patient_id: str) -> bool:
    try:
        config.s3().head_object(Bucket=config.S3_BUCKET, Key=_key(patient_id))
        return True
    except Exception:
        return False


def list_versions(patient_id: str) -> List[Dict[str, Any]]:
    """Returns versions newest first."""
    resp = config.s3().list_object_versions(
        Bucket=config.S3_BUCKET, Prefix=_key(patient_id))
    versions = resp.get("Versions", [])
    versions.sort(key=lambda v: v.get("LastModified") or 0, reverse=True)
    out = []
    for v in versions:
        out.append({
            "version_id": v.get("VersionId", "null"),
            "is_latest": bool(v.get("IsLatest")),
            "last_modified": (v["LastModified"].astimezone(timezone.utc).isoformat()
                              if v.get("LastModified") else ""),
            "size": v.get("Size", 0),
        })
    return out


def append_note(patient_id: str, author: str, note_text: str) -> Dict[str, Any]:
    """Read latest, append a note, write a new version. Returns new version_id."""
    record = get_record(patient_id)
    record.setdefault("clinical_notes", [])
    record["clinical_notes"].append({
        "author": author,
        "text": note_text,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return put_record(patient_id, record)


def empty_initial_record(patient_id: str, full_name: str = "",
                         email: str = "") -> Dict[str, Any]:
    return {
        "patient_id": patient_id,
        "full_name": full_name,
        "email": email,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "blood_type": None,
        "allergies": [],
        "conditions": [],
        "medications": [],
        "encounters": [],
        "clinical_notes": [],
    }
