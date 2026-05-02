"""Doctor dashboard: scoped record access + add clinical notes."""
import json
from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app.api_gateway_client import call
from cloud import policy_store, users, notifications, access_requests

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
    patients = users.list_by_role("patient")
    record = session.pop("last_record", None)
    # Safety: ensure old session data doesn't break the new structured view
    if record and "data" not in record:
        record = None
        
    last_error = session.pop("last_error", None)
    return render_template("doctor_dashboard.html",
                           user=user, my_grants=my_grants, patients=patients,
                           record=record, last_error=last_error)


@bp.route("/request-record", methods=["POST"])
@require_doctor
def request_record():
    user = session["user"]
    patient_id = request.form["patient_id"]
    r = call("POST", "request-record", user["token"], {"patient_id": patient_id})
    if r["status"] == 200:
        record_data = r["body"]["record"]
        session["last_record"] = {
            "patient": patient_id,
            "data": record_data, # Store the actual dict
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


@bp.route("/request-access", methods=["POST"])
@require_doctor
def request_access():
    user = session["user"]
    patient_id = request.form["patient_id"]
    scope = request.form.get("scope", "read")
    ttl = int(request.form.get("ttl_seconds", 86400))
    
    # Create formal request record
    access_requests.create(patient_id, user["username"], scope, ttl)
    
    # Send notification to patient
    msg = (f"Dr. {user['username']} is requesting {scope} access to your record "
           f"for {ttl // 3600} hours.")
    notifications.push(patient_id, msg, link="/patient/")
    
    flash(f"Access request sent to {patient_id}. You will be notified when it is reviewed.", "info")
    return redirect(url_for("doctor.dashboard"))


@bp.route("/download-report")
@require_doctor
def download_report():
    user = session["user"]
    patient_id = request.args.get("patient_id")
    s3_key = request.args.get("s3_key")
    filename = request.args.get("filename")
    
    if not patient_id or not s3_key:
        flash("Invalid report request.", "error")
        return redirect(url_for("doctor.dashboard"))
        
    # VERIFY: Does the doctor have access to this patient?
    grant = policy_store.lookup(patient_id, user["username"])
    if not grant:
        flash("You do not have access to this patient's records.", "error")
        return redirect(url_for("doctor.dashboard"))
        
    # Fetch from S3
    from cloud import config
    try:
        obj = config.s3().get_object(Bucket=config.S3_BUCKET, Key=s3_key)
        from flask import Response
        return Response(
            obj["Body"].read(),
            mimetype=obj.get("ContentType", "application/octet-stream"),
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        flash(f"Failed to download report: {e}", "error")
        return redirect(url_for("doctor.dashboard"))
