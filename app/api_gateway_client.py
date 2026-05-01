"""Thin client that calls the smart-contract Lambda via API Gateway.

If the API Gateway URL is not yet provisioned, falls back to invoking the
Lambda directly through boto3 (same Lambda, same logic — only the network
hop changes), so the demo still works during early bootstrapping.
"""
import json
import os
from typing import Any, Dict, Optional

import requests

from cloud import config

_API_BASE = None


def _api_base():
    global _API_BASE
    if _API_BASE:
        return _API_BASE
    path = os.path.join(os.path.dirname(__file__), "..", ".localstack", "api_gateway.json")
    if os.path.exists(path):
        with open(path) as f:
            _API_BASE = json.load(f)["base_url"]
    return _API_BASE


def call(method: str, route: str, token: str,
         body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    base = _api_base()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if base:
        url = f"{base}/{route}"
        try:
            if method == "POST":
                r = requests.post(url, json=body or {}, headers=headers, timeout=10)
            else:
                r = requests.get(url, headers=headers, timeout=10)
            return {"status": r.status_code, "body": r.json() if r.text else {}}
        except Exception:
            pass
    # Fallback: direct Lambda invoke
    return _invoke_lambda_direct(method, route, token, body or {})


def _invoke_lambda_direct(method: str, route: str, token: str,
                          body: Dict[str, Any]) -> Dict[str, Any]:
    payload = {
        "httpMethod": method,
        "path": f"/{route}",
        "headers": {"authorization": f"Bearer {token}"},
        "body": json.dumps(body),
        "isBase64Encoded": False,
    }
    r = config.lambda_().invoke(
        FunctionName=config.LAMBDA_SMART_CONTRACT,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload).encode(),
    )
    raw = json.loads(r["Payload"].read())
    body_str = raw.get("body", "{}")
    try:
        body_json = json.loads(body_str)
    except Exception:
        body_json = {"raw": body_str}
    return {"status": int(raw.get("statusCode", 500)), "body": body_json}
