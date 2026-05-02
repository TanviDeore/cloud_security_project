"""Smart-contract Lambda. API Gateway routes:

  POST /grant            { patient_id, doctor_id, scope?, ttl_seconds? }
  POST /revoke           { patient_id, doctor_id }
  POST /request-record   { patient_id }
  POST /add-note         { patient_id, note }
  GET  /view-history     ?patient_id=...
  GET  /audit
  GET  /verify-chain
  POST /verify-npi       (admin) { username, npi, first_name, last_name, state }
  POST /approve-doctor   (admin) { username }
  POST /reject-doctor    (admin) { username, reason? }

Auth: HS512 JWT in Authorization: Bearer header, signed with the key in
Secrets Manager. Claims: { sub: username, role: patient|doctor|admin, exp }.
"""
import base64
import json
import os
import time
from decimal import Decimal
from typing import Any, Dict

import jwt as pyjwt

from cloud import (cloudwatch_logger, ledger, notifications, npi_client,
                   policy_store, s3_store, users)
from cloud.secrets_client import jwt_signing_key

from rbac_policy import evaluate


class _DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return int(o) if o == int(o) else float(o)
        return super().default(o)


def _resp(status: int, body: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, cls=_DecimalEncoder),
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
        if method == "POST" and route == "add-note":
            return _add_note(principal, body)
        if method == "GET" and route == "view-history":
            return _view_history(principal, event)
        if method == "GET" and route == "audit":
            return _audit(principal)
        if method == "GET" and route == "verify-chain":
            return _verify_chain()
        if method == "POST" and route == "verify-npi":
            return _verify_npi(principal, body)
        if method == "POST" and route == "approve-doctor":
            return _approve_doctor(principal, body)
        if method == "POST" and route == "reject-doctor":
            return _reject_doctor(principal, body)
    except Exception as e:
        return _resp(500, {"error": "internal", "detail": str(e)})

    return _resp(404, {"error": "no such route", "route": route})


def _human_duration(seconds: int) -> str:
    if seconds <= 0:
        return "now"
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h { (seconds % 3600) // 60 }m"
    return f"{seconds // 86400}d"


# ---------------------------------------------------------------- patient ---

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
                           patient=patient_id, doctor=doctor_id, scope=scope)
    notifications.push(doctor_id,
                       f"{patient_id} granted you '{scope}' access (expires "
                       f"in {_human_duration(ttl)})", link="/doctor/")
    notifications.push(patient_id,
                       f"You granted {doctor_id} '{scope}' access",
                       link="/patient/")
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
    notifications.push(doctor_id,
                       f"{patient_id} revoked your access", link="/doctor/")
    notifications.push(patient_id,
                       f"You revoked {doctor_id}'s access", link="/patient/")
    return _resp(200, {"revoked": True, "block": blk["block_id"]})


# ----------------------------------------------------------------- doctor ---

def _request_record(principal, body):
    patient_id = body.get("patient_id")
    resource = f"patient::{patient_id}"
    grant_item = policy_store.lookup(patient_id, principal["username"])
    allowed, why = evaluate(principal, "request-record", resource,
                            {"GrantExists": grant_item is not None})
    if not allowed:
        reason = "No active grant found for this patient (access may be expired or revoked)" if not grant_item else why
        return _deny(principal["username"], "request-record", resource, reason)
    if not policy_store.scope_includes(grant_item.get("scope", "read"), "read"):
        return _deny(principal["username"], "request-record", resource,
                     f"Your current grant scope ({grant_item.get('scope')}) does not include 'read' access.")
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
    notifications.push(patient_id,
                       f"Dr. {principal['username']} accessed your record",
                       link="/patient/")
    return _resp(200, {"record": record, "block": blk["block_id"],
                       "scope": grant_item.get("scope"),
                       "expires_at": grant_item["expires_at"]})


def _add_note(principal, body):
    patient_id = body.get("patient_id")
    note_text = (body.get("note") or "").strip()
    resource = f"patient::{patient_id}"
    if not note_text:
        return _resp(400, {"error": "empty note"})
    grant_item = policy_store.lookup(patient_id, principal["username"])
    allowed, why = evaluate(principal, "add-note", resource,
                            {"GrantExists": grant_item is not None})
    if not allowed:
        reason = "No active grant found for this patient (access may be expired or revoked)" if not grant_item else why
        return _deny(principal["username"], "add-note", resource, reason)
    if not policy_store.scope_includes(grant_item.get("scope", "read"), "write"):
        return _deny(principal["username"], "add-note", resource,
                     f"Your current grant scope ({grant_item.get('scope')}) is read-only — "
                     "you need 'write' or 'history' access to add notes.")
    put = s3_store.append_note(patient_id, principal["username"], note_text)
    blk = ledger.append_block(
        actor=principal["username"], action="UPDATE_RECORD", resource=resource,
        details={"version_id": put["version_id"],
                 "note_excerpt": note_text[:120]})
    cloudwatch_logger.emit("UPDATE_RECORD", actor=principal["username"],
                           patient=patient_id, version=put["version_id"])
    notifications.push(patient_id,
                       f"Dr. {principal['username']} added a note "
                       f"(record version {put['version_id'][:8]}…)",
                       link="/patient/")
    return _resp(200, {"version_id": put["version_id"], "block": blk["block_id"]})


def _view_history(principal, event):
    qs = (event.get("queryStringParameters") or {}) if event else {}
    patient_id = (qs or {}).get("patient_id", principal["username"])
    resource = f"patient::{patient_id}"
    if principal["role"] == "patient" and principal["username"] != patient_id:
        return _deny(principal["username"], "view-history", resource,
                     "patient may only view own history")
    if principal["role"] == "doctor":
        grant_item = policy_store.lookup(patient_id, principal["username"])
        allowed, why = evaluate(principal, "view-history", resource,
                                {"GrantExists": grant_item is not None})
        if not allowed:
            return _deny(principal["username"], "view-history", resource, why)
        if not policy_store.scope_includes(grant_item.get("scope", "read"), "read"):
            return _deny(principal["username"], "view-history", resource,
                         f"grant scope '{grant_item.get('scope')}' does not include 'read'")
    versions = s3_store.list_versions(patient_id)
    return _resp(200, {"versions": versions})


# ------------------------------------------------------------------ admin ---

def _verify_npi(principal, body):
    if principal["role"] != "admin":
        return _deny(principal["username"], "verify-npi",
                     f"user::{body.get('username')}",
                     "only admin may run NPI verification")
    result = npi_client.verify(
        body.get("npi", ""), body.get("first_name", ""),
        body.get("last_name", ""), body.get("state", ""))
    blk = ledger.append_block(
        actor=principal["username"], action="NPI_VERIFY",
        resource=f"user::{body.get('username','')}",
        details={"valid": bool(result.get("valid")),
                 "source": result.get("source"),
                 "npi": body.get("npi")})
    return _resp(200, {"result": result, "block": blk["block_id"]})


def _approve_doctor(principal, body):
    if principal["role"] != "admin":
        return _deny(principal["username"], "approve-doctor",
                     f"user::{body.get('username')}",
                     "only admin may approve doctors")
    target = body.get("username")
    user = users.get(target)
    if not user or user.get("role") != "doctor":
        return _resp(404, {"error": "user not found or not a doctor"})
    users.set_status(target, "active")
    users.set_npi_verified(target, True)
    blk = ledger.append_block(
        actor=principal["username"], action="APPROVE_DOCTOR",
        resource=f"user::{target}", details={"approved_by": principal["username"]})
    notifications.push(target,
                       "Your doctor account was approved. You may now log in.",
                       link="/login")
    return _resp(200, {"approved": True, "block": blk["block_id"]})


def _reject_doctor(principal, body):
    if principal["role"] != "admin":
        return _deny(principal["username"], "reject-doctor",
                     f"user::{body.get('username')}",
                     "only admin may reject doctors")
    target = body.get("username")
    reason = body.get("reason", "")
    users.set_status(target, "rejected")
    users.set_npi_verified(target, False)
    blk = ledger.append_block(
        actor=principal["username"], action="REJECT_DOCTOR",
        resource=f"user::{target}",
        details={"reason": reason, "rejected_by": principal["username"]})
    notifications.push(target,
                       f"Your doctor account was rejected: {reason}",
                       link="/login")
    return _resp(200, {"rejected": True, "block": blk["block_id"]})


# ------------------------------------------------------------------- read ---

def _audit(principal):
    blocks = list(ledger.all_blocks())
    if principal["role"] == "patient":
        # patients see only blocks against their own record
        mine = f"patient::{principal['username']}"
        blocks = [b for b in blocks if b["resource"] == mine]
    elif principal["role"] == "doctor":
        # doctors see only blocks where they were the actor
        blocks = [b for b in blocks if b["actor"] == principal["username"]]
    # admins see everything
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
