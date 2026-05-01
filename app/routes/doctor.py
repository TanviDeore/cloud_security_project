"""Doctor dashboard: scoped record access + add clinical notes."""
import json
from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app.api_gateway_client import call
from cloud import policy_store

bp = Blueprint("doctor", __name__)


def require_doctor(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        u = session.get("user")
        if not u or u["role"] != "doctor":
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return wrapper


@bp.route("/")
@require_doctor
def dashboard():
    user = session["user"]
    my_grants = policy_store.list_grants_for_doctor(user["username"])
    record = session.pop("last_record", None)
    last_error = session.pop("last_error", None)
    return render_template("doctor_dashboard.html",
                           user=user, my_grants=my_grants,
                           record=record, last_error=last_error)


@bp.route("/request-record", methods=["POST"])
@require_doctor
def request_record():
    user = session["user"]
    patient_id = request.form["patient_id"]
    r = call("POST", "request-record", user["token"], {"patient_id": patient_id})
    if r["status"] == 200:
        session["last_record"] = {
            "patient": patient_id,
            "json": json.dumps(r["body"]["record"], indent=2),
            "block": r["body"]["block"],
            "scope": r["body"].get("scope"),
        }
        flash(f"Record retrieved (audit block #{r['body']['block']}, scope "
              f"{r['body'].get('scope')}).", "info")
    else:
        session["last_error"] = r["body"]
        flash(f"Denied: {r['body'].get('reason', r['body'])}", "error")
    return redirect(url_for("doctor.dashboard"))


@bp.route("/add-note", methods=["POST"])
@require_doctor
def add_note():
    user = session["user"]
    patient_id = request.form["patient_id"]
    note = request.form["note"]
    r = call("POST", "add-note", user["token"],
             {"patient_id": patient_id, "note": note})
    if r["status"] == 200:
        flash(f"Note added (S3 version {r['body']['version_id'][:10]}…, "
              f"audit block #{r['body']['block']}).", "info")
    else:
        flash(f"Could not add note: {r['body'].get('reason', r['body'])}",
              "error")
    return redirect(url_for("doctor.dashboard"))
