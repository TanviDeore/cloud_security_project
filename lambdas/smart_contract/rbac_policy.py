"""IAM-style declarative policy evaluator.

Policies are JSON like:
  {
    "Version": "2026-04-30",
    "Statement": [
      {"Effect":"Allow","Principal":{"role":"patient"},"Action":["grant","revoke"],
       "Resource":"patient::self"},
      {"Effect":"Allow","Principal":{"role":"doctor"},"Action":["request-record"],
       "Resource":"patient::*","Condition":{"GrantExists":true}}
    ]
  }

The evaluator returns ALLOW/DENY plus the matching statement for auditability.
"""
from typing import Any, Dict, Tuple

DEFAULT_POLICY: Dict[str, Any] = {
    "Version": "2026-04-30",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"role": "patient"},
            "Action": ["grant", "revoke", "audit", "verify-chain"],
            "Resource": "patient::self",
        },
        {
            "Effect": "Allow",
            "Principal": {"role": "doctor"},
            "Action": ["request-record"],
            "Resource": "patient::*",
            "Condition": {"GrantExists": True},
        },
        {
            "Effect": "Allow",
            "Principal": {"role": "*"},
            "Action": ["audit", "verify-chain"],
            "Resource": "ledger::*",
        },
    ],
}


def evaluate(principal: Dict[str, str], action: str, resource: str,
             context: Dict[str, Any], policy: Dict[str, Any] = DEFAULT_POLICY
             ) -> Tuple[bool, str]:
    for stmt in policy["Statement"]:
        if stmt["Principal"]["role"] not in (principal.get("role"), "*"):
            continue
        if action not in stmt["Action"]:
            continue
        if not _resource_match(stmt["Resource"], resource, principal):
            continue
        if not _conditions_match(stmt.get("Condition", {}), context):
            continue
        if stmt["Effect"] == "Allow":
            return True, f"matched: {stmt}"
        return False, f"explicit deny: {stmt}"
    return False, "no matching Allow statement"


def _resource_match(pattern: str, resource: str, principal: Dict[str, str]) -> bool:
    if pattern == resource:
        return True
    if pattern.endswith("::*") and resource.startswith(pattern[:-1]):
        return True
    if pattern == "patient::self":
        return resource == f"patient::{principal.get('username')}"
    return False


def _conditions_match(conds: Dict[str, Any], context: Dict[str, Any]) -> bool:
    for key, expected in conds.items():
        if context.get(key) != expected:
            return False
    return True
