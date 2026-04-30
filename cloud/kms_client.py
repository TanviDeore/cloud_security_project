"""KMS-backed envelope encryption helpers.

Envelope crypto: KMS generates a 256-bit data key, returns it both in plaintext
(used immediately to encrypt the EHR with AES-256-GCM) and ciphertext (stored
alongside the encrypted EHR). Decryption requires KMS to unwrap the data key,
so revoking the CMK revokes access to every record encrypted under it.
"""
import os
from typing import Tuple
from . import config


def generate_data_key() -> Tuple[bytes, bytes]:
    """Returns (plaintext_key, ciphertext_key)."""
    resp = config.kms().generate_data_key(
        KeyId=config.KMS_KEY_ALIAS, KeySpec="AES_256"
    )
    return resp["Plaintext"], resp["CiphertextBlob"]


def decrypt_data_key(ciphertext_key: bytes) -> bytes:
    resp = config.kms().decrypt(
        CiphertextBlob=ciphertext_key, KeyId=config.KMS_KEY_ALIAS
    )
    return resp["Plaintext"]


def describe_key() -> dict:
    return config.kms().describe_key(KeyId=config.KMS_KEY_ALIAS)["KeyMetadata"]
