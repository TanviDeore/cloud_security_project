"""Identity service.

In production this wraps Amazon Cognito. LocalStack Community Edition does
not implement cognito-idp, so we implement the same login surface against
our own Users DynamoDB table — bcrypt-hashed passwords + lockout counters.
The same code path is used for production Cognito if the deployment switches
to Pro / real AWS (the Cognito branch is preserved below).
"""
import json
import os
from functools import lru_cache
from typing import Any, Dict, List, Optional

from . import config, passwords, users

_COGNITO_FILE = os.path.join(os.path.dirname(__file__), "..", ".localstack", "cognito.json")


@lru_cache(maxsize=1)
def _backend_meta() -> Dict[str, Any]:
    if os.path.exists(_COGNITO_FILE):
        with open(_COGNITO_FILE) as f:
            data = json.load(f)
        if data.get("backend") == "cognito":
            return data
    return {"backend": "ddb-users"}


def login(username: str, password: str) -> Dict[str, Any]:
    """Returns {ok, user?, reason?} — never raises on bad input."""
    meta = _backend_meta()

    if meta.get("backend") == "cognito":
        try:
            resp = config.cognito().admin_initiate_auth(
                UserPoolId=meta["pool_id"], ClientId=meta["client_id"],
                AuthFlow="ADMIN_NO_SRP_AUTH",
                AuthParameters={"USERNAME": username, "PASSWORD": password},
            )
            return {"ok": True, "user": {
                "username": username,
                "role": _cognito_role(username, meta["pool_id"]) or "patient",
                "cognito_token": resp["AuthenticationResult"]["AccessToken"],
            }}
        except Exception:
            return {"ok": False, "reason": "Invalid credentials"}

    # DynamoDB-backed identity (the default path on LocalStack Community)
    user = users.get(username)
    if not user:
        return {"ok": False, "reason": "Invalid credentials"}
    if user.get("status") == "pending_review":
        return {"ok": False,
                "reason": "Account pending administrator approval"}
    if user.get("status") == "rejected":
        return {"ok": False, "reason": "Account was rejected"}
    if users.is_locked(user):
        return {"ok": False,
                "reason": ("Account locked after too many failed attempts. "
                           "Try again later.")}
    if not passwords.verify_password(password, user.get("password_hash", "")):
        state = users.update_failed_attempt(username)
        if int(state["locked_until"]) > 0:
            return {"ok": False,
                    "reason": ("Too many failed attempts — account locked "
                               "for 15 minutes")}
        return {"ok": False, "reason": "Invalid credentials"}
    users.reset_attempts(username)
    return {"ok": True, "user": {
        "username": user["username"],
        "role": user["role"],
        "email": user.get("email", ""),
    }}


def list_users() -> List[Dict[str, str]]:
    meta = _backend_meta()
    if meta.get("backend") == "cognito":
        try:
            resp = config.cognito().list_users(UserPoolId=meta["pool_id"], Limit=60)
        except Exception:
            return []
        out = []
        for u in resp.get("Users", []):
            role = "patient"
            for a in u.get("Attributes", []):
                if a["Name"] == "custom:role":
                    role = a["Value"]
            out.append({"username": u["Username"], "role": role,
                        "status": "active"})
        return out
    return [{"username": u["username"], "role": u["role"],
             "status": u.get("status", "active")}
            for u in users.all_users()]


def _cognito_role(username: str, pool_id: str) -> Optional[str]:
    try:
        resp = config.cognito().admin_get_user(UserPoolId=pool_id, Username=username)
    except Exception:
        return None
    for attr in resp.get("UserAttributes", []):
        if attr["Name"] == "custom:role":
            return attr["Value"]
    return None
