"""Cognito-backed login. Issues a Cognito session token, then we mint a
short-lived JWT signed with the Secrets Manager key for downstream calls."""
import json
import os
from functools import lru_cache
from typing import Optional, Tuple

from . import config


@lru_cache(maxsize=1)
def _ids() -> Tuple[str, str]:
    """Loads pool_id + client_id written by infra/create_cognito_pool.sh."""
    path = os.path.join(os.path.dirname(__file__), "..", ".localstack", "cognito.json")
    with open(path) as f:
        data = json.load(f)
    return data["pool_id"], data["client_id"]


def login(username: str, password: str) -> Optional[dict]:
    pool_id, client_id = _ids()
    try:
        resp = config.cognito().admin_initiate_auth(
            UserPoolId=pool_id,
            ClientId=client_id,
            AuthFlow="ADMIN_NO_SRP_AUTH",
            AuthParameters={"USERNAME": username, "PASSWORD": password},
        )
    except Exception:
        return None

    role = _get_role(username) or "patient"
    return {
        "username": username,
        "role": role,
        "cognito_token": resp["AuthenticationResult"]["AccessToken"],
    }


def _get_role(username: str) -> Optional[str]:
    pool_id, _ = _ids()
    try:
        resp = config.cognito().admin_get_user(UserPoolId=pool_id, Username=username)
    except Exception:
        return None
    for attr in resp.get("UserAttributes", []):
        if attr["Name"] == "custom:role":
            return attr["Value"]
    return None


def list_users():
    pool_id, _ = _ids()
    try:
        resp = config.cognito().list_users(UserPoolId=pool_id, Limit=60)
    except Exception:
        return []
    out = []
    for u in resp.get("Users", []):
        role = None
        for a in u.get("Attributes", []):
            if a["Name"] == "custom:role":
                role = a["Value"]
        out.append({"username": u["Username"], "role": role or "patient"})
    return out
