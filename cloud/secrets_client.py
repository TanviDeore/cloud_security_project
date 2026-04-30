"""Reads JWT signing key from Secrets Manager (cached process-wide)."""
import json
from functools import lru_cache

from . import config


@lru_cache(maxsize=1)
def jwt_signing_key() -> str:
    resp = config.secrets().get_secret_value(SecretId=config.SECRET_NAME)
    return json.loads(resp["SecretString"])["key"]
