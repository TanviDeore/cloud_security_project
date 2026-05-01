"""Patient dashboard: record + scoped grants + chain status + activity."""
from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app.api_gateway_client import call
from cloud import cognito_client, policy_store, s3_store

bp = Blueprint("patient", __name__)

DURATIONS = [
    ("1 hour",   3600),
    ("8 hours",  8 * 3600),
    ("24 hours", 86400),
    ("7 days",   7 * 86400),
    ("30 days",  30 * 86400),
]
SCOPES = [
    ("Read only — view record + history",      "read"),
    ("Read + write — append clinical notes",   "write"),
]


def require_patient(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        u = session.get("user")
        if not u or u["role"] != "patient":
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return wrapper


@bp.route("/")
@require_patient
def dashboard():
    user = session["user"]

    # The patient's own decrypted record
    try:
        record = s3_store.get_record(user["username"])
    except Exception:
        record = None

    grants = policy_store.list_grants(user["username"])
    doctors = [u for u in cognito_client.list_users()
               if u["role"] == "doctor" and u.get("status") == "active"]

    # Audit + chain status (Lambda enforces patient-scoping server-side)
    audit = call("GET", "audit", user["token"])
    blocks = audit["body"].get("blocks", []) if audit["status"] == 200 else []
    # Filter to actions taken BY a doctor on this record (drop the patient's own grants)
    doctor_blocks = [b for b in blocks if b["actor"] != user["username"]]

    chain = call("GET", "verify-chain", user["token"])
    chain_state = chain["body"] if chain["status"] == 200 else {"valid": False}

    return render_template("patient_dashboard.html",
                           user=user, record=record, grants=grants,
                           doctors=doctors, doctor_blocks=doctor_blocks,
                           chain=chain_state,
                           durations=DURATIONS, scopes=SCOPES)


@bp.route("/grant", methods=["POST"])
@require_patient
def grant():
    user = session["user"]
    doctor_id = request.form["doctor_id"]
    ttl = int(request.form.get("ttl_seconds", 86400))
    scope = request.form.get("scope", "read")
    r = call("POST", "grant", user["token"],
             {"patient_id": user["username"], "doctor_id": doctor_id,
              "ttl_seconds": ttl, "scope": scope})
    flash(f"Granted {scope} access to {doctor_id}." if r["status"] == 200
          else f"Grant failed: {r['body']}",
          "info" if r["status"] == 200 else "error")
    return redirect(url_for("patient.dashboard"))


@bp.route("/revoke", methods=["POST"])
@require_patient
def revoke():
    user = session["user"]
    doctor_id = request.form["doctor_id"]
    r = call("POST", "revoke", user["token"],
             {"patient_id": user["username"], "doctor_id": doctor_id})
    flash("Access revoked." if r["status"] == 200
          else f"Revoke failed: {r['body']}",
          "info" if r["status"] == 200 else "error")
    return redirect(url_for("patient.dashboard"))
