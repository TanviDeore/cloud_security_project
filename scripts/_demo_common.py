"""Shared helpers for demo scripts: mint a JWT, call API Gateway / Lambda."""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import jwt as pyjwt

from cloud.secrets_client import jwt_signing_key
from app.api_gateway_client import call as api_call


def token_for(username: str, role: str, ttl: int = 3600) -> str:
    now = int(time.time())
    return pyjwt.encode(
        {"sub": username, "role": role, "iat": now, "exp": now + ttl},
        jwt_signing_key(),
        algorithm="HS512",
    )


def hr(title: str = ""):
    bar = "=" * 78
    print()
    print(bar)
    if title:
        print(f"  {title}")
        print(bar)


def show(label: str, resp):
    print(f"\n[{label}] HTTP {resp['status']}")
    print(json.dumps(resp["body"], indent=2)[:1200])


def call(method: str, route: str, token: str, body=None):
    return api_call(method, route, token, body)
