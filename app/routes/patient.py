"""Patient dashboard: grant/revoke access; view who accessed your record."""
from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app.api_gateway_client import call
from cloud import cognito_client, policy_store

bp = Blueprint("patient", __name__)


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
    grants = policy_store.list_grants(user["username"])
    doctors = [u for u in cognito_client.list_users() if u["role"] == "doctor"]
    audit = call("GET", "audit", user["token"])
    blocks = audit["body"].get("blocks", []) if audit["status"] == 200 else []
    return render_template("patient_dashboard.html",
                           user=user, grants=grants, doctors=doctors,
                           blocks=blocks)


@bp.route("/grant", methods=["POST"])
@require_patient
def grant():
    user = session["user"]
    doctor_id = request.form["doctor_id"]
    ttl = int(request.form.get("ttl_seconds", 86400))
    r = call("POST", "grant", user["token"],
             {"patient_id": user["username"], "doctor_id": doctor_id,
              "ttl_seconds": ttl, "scope": "read"})
    flash("Access granted." if r["status"] == 200
          else f"Grant failed: {r['body']}", "info" if r["status"] == 200 else "error")
    return redirect(url_for("patient.dashboard"))


@bp.route("/revoke", methods=["POST"])
@require_patient
def revoke():
    user = session["user"]
    doctor_id = request.form["doctor_id"]
    r = call("POST", "revoke", user["token"],
             {"patient_id": user["username"], "doctor_id": doctor_id})
    flash("Access revoked." if r["status"] == 200
          else f"Revoke failed: {r['body']}", "info" if r["status"] == 200 else "error")
    return redirect(url_for("patient.dashboard"))
