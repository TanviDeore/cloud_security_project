"""EHR storage on S3 with KMS envelope encryption.

Object layout in S3:
  Key:      patients/{patient_id}.ehr
  Body:     12-byte nonce || GCM ciphertext || 16-byte tag
  Metadata: x-amz-meta-edk = base64(encrypted-data-key)
            x-amz-meta-alg = AES-256-GCM

The bucket also has SSE-KMS as a defense-in-depth layer; even if envelope
crypto were bypassed, the raw S3 storage is still encrypted at rest.
"""
import base64
import json
import os
from typing import Any, Dict

from Crypto.Cipher import AES

from . import config, kms_client

NONCE_BYTES = 12


def _key(patient_id: str) -> str:
    return f"patients/{patient_id}.ehr"


def put_record(patient_id: str, record: Dict[str, Any]) -> None:
    plaintext = json.dumps(record, separators=(",", ":")).encode()
    data_key, edk = kms_client.generate_data_key()
    nonce = os.urandom(NONCE_BYTES)
    cipher = AES.new(data_key, AES.MODE_GCM, nonce=nonce)
    ct, tag = cipher.encrypt_and_digest(plaintext)
    body = nonce + ct + tag
    config.s3().put_object(
        Bucket=config.S3_BUCKET,
        Key=_key(patient_id),
        Body=body,
        Metadata={
            "edk": base64.b64encode(edk).decode(),
            "alg": "AES-256-GCM",
        },
        ContentType="application/octet-stream",
    )


def get_record(patient_id: str) -> Dict[str, Any]:
    obj = config.s3().get_object(Bucket=config.S3_BUCKET, Key=_key(patient_id))
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
