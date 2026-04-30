"""Smart-contract Lambda. Routed via API Gateway:
  POST /grant            { patient_id, doctor_id, scope?, ttl_seconds? }
  POST /revoke           { patient_id, doctor_id }
  POST /request-record   { patient_id }
  GET  /audit
  GET  /verify-chain

Auth: HS512 JWT in Authorization: Bearer header, signed with the key in
Secrets Manager. Claims: { sub: username, role: patient|doctor, exp }.
"""
import base64
import json
import os
import time
from typing import Any, Dict

import jwt as pyjwt

from cloud import cloudwatch_logger, ledger, policy_store, s3_store
from cloud.secrets_client import jwt_signing_key

from rbac_policy import evaluate


def _resp(status: int, body: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _decode_jwt(headers: Dict[str, str]):
    auth = headers.get("authorization") or headers.get("Authorization") or ""
    if not auth.startswith("Bearer "):
        return None, "missing bearer token"
    token = auth[len("Bearer "):]
    try:
        claims = pyjwt.decode(token, jwt_signing_key(), algorithms=["HS512"])
        return claims, None
    except pyjwt.ExpiredSignatureError:
        return None, "token expired"
    except Exception as e:
        return None, f"invalid token: {e}"


def _parse_body(event: Dict[str, Any]) -> Dict[str, Any]:
    body = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode()
    if isinstance(body, str):
        try:
            return json.loads(body)
        except Exception:
            return {}
    return body or {}


def _route(event: Dict[str, Any]):
    method = (event.get("httpMethod") or event.get("requestContext", {})
              .get("http", {}).get("method") or "GET").upper()
    path = event.get("path") or event.get("rawPath") or ""
    return method, path.rstrip("/").rsplit("/", 1)[-1]


def _deny(actor: str, action: str, resource: str, reason: str):
    cloudwatch_logger.emit("ACCESS_DENIED", actor=actor, action=action,
                           resource=resource, reason=reason)
    ledger.append_block(actor=actor or "anonymous",
                        action="ACCESS_DENIED",
                        resource=resource,
                        details={"reason": reason, "intended_action": action})
    return _resp(403, {"error": "ACCESS_DENIED", "reason": reason})


def lambda_handler(event, context):
    method, route = _route(event)

    claims, err = _decode_jwt(event.get("headers") or {})
    if err and route != "verify-chain":
        return _deny("anonymous", route, "unknown", err)

    principal = {
        "username": (claims or {}).get("sub", "anonymous"),
        "role": (claims or {}).get("role", "guest"),
    }
    body = _parse_body(event)

    try:
        if method == "POST" and route == "grant":
            return _grant(principal, body)
        if method == "POST" and route == "revoke":
            return _revoke(principal, body)
        if method == "POST" and route == "request-record":
            return _request_record(principal, body)
        if method == "GET" and route == "audit":
            return _audit(principal)
        if method == "GET" and route == "verify-chain":
            return _verify_chain()
    except Exception as e:
        return _resp(500, {"error": "internal", "detail": str(e)})

    return _resp(404, {"error": "no such route", "route": route})


def _grant(principal, body):
    patient_id = body.get("patient_id")
    doctor_id = body.get("doctor_id")
    scope = body.get("scope", "read")
    ttl = int(body.get("ttl_seconds", 86400))
    resource = f"patient::{patient_id}"
    allowed, why = evaluate(principal, "grant", resource, {})
    if not allowed or principal["username"] != patient_id:
        return _deny(principal["username"], "grant", resource,
                     why if not allowed else "patient may only grant on own record")
    item = policy_store.grant(patient_id, doctor_id, scope, ttl)
    blk = ledger.append_block(actor=principal["username"], action="GRANT",
                              resource=resource,
                              details={"doctor": doctor_id, "scope": scope,
                                       "ttl_seconds": ttl})
    cloudwatch_logger.emit("GRANT", actor=principal["username"],
                           patient=patient_id, doctor=doctor_id)
    return _resp(200, {"granted": item, "block": blk["block_id"]})


def _revoke(principal, body):
    patient_id = body.get("patient_id")
    doctor_id = body.get("doctor_id")
    resource = f"patient::{patient_id}"
    allowed, why = evaluate(principal, "revoke", resource, {})
    if not allowed or principal["username"] != patient_id:
        return _deny(principal["username"], "revoke", resource,
                     why if not allowed else "patient may only revoke on own record")
    policy_store.revoke(patient_id, doctor_id)
    blk = ledger.append_block(actor=principal["username"], action="REVOKE",
                              resource=resource,
                              details={"doctor": doctor_id})
    cloudwatch_logger.emit("REVOKE", actor=principal["username"],
                           patient=patient_id, doctor=doctor_id)
    return _resp(200, {"revoked": True, "block": blk["block_id"]})


def _request_record(principal, body):
    patient_id = body.get("patient_id")
    resource = f"patient::{patient_id}"
    grant_item = policy_store.lookup(patient_id, principal["username"])
    allowed, why = evaluate(principal, "request-record", resource,
                            {"GrantExists": grant_item is not None})
    if not allowed:
        return _deny(principal["username"], "request-record", resource, why)
    try:
        record = s3_store.get_record(patient_id)
    except Exception as e:
        return _deny(principal["username"], "request-record", resource,
                     f"record fetch failed: {e}")
    blk = ledger.append_block(actor=principal["username"], action="RECORD_FETCH",
                              resource=resource,
                              details={"scope": grant_item.get("scope")})
    cloudwatch_logger.emit("RECORD_FETCH", actor=principal["username"],
                           patient=patient_id)
    return _resp(200, {"record": record, "block": blk["block_id"],
                       "expires_at": grant_item["expires_at"]})


def _audit(principal):
    blocks = list(ledger.all_blocks())
    if principal["role"] == "patient":
        # Patients only see blocks about their own record
        mine = f"patient::{principal['username']}"
        blocks = [b for b in blocks if b["resource"] == mine]
    return _resp(200, {"blocks": [_serialize_block(b) for b in blocks]})


def _verify_chain():
    return _resp(200, ledger.verify_chain())


def _serialize_block(b):
    return {
        "block_id": int(b["block_id"]),
        "timestamp": b["timestamp"],
        "actor": b["actor"],
        "action": b["action"],
        "resource": b["resource"],
        "details": b["details"],
        "prev_hash": b["prev_hash"],
        "hash": b["hash"],
    }
