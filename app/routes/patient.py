"""Patient dashboard: record + scoped grants + chain status + activity."""
from datetime import datetime, timezone
from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app.api_gateway_client import call
from cloud import ledger, policy_store, s3_store, access_requests, notifications
from cloud import cognito_client

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

    # Fetch pending access requests
    requests = [r for r in access_requests.list_for_patient(user["username"]) 
                if r["status"] == "PENDING"]

    return render_template("patient_dashboard.html",
                           user=user, record=record, grants=grants,
                           doctors=doctors, doctor_blocks=doctor_blocks,
                           chain=chain_state, pending_requests=requests,
                           durations=DURATIONS, scopes=SCOPES)


@bp.route("/approve-request", methods=["POST"])
@require_patient
def approve_request():
    user = session["user"]
    req_id = request.form["request_id"]
    req = access_requests.get(user["username"], req_id)
    
    if not req or req["status"] != "PENDING":
        flash("Request not found or already processed.", "error")
        return redirect(url_for("patient.dashboard"))

    # Issue the grant (same logic as /grant but from request)
    existing = policy_store.lookup(user["username"], req["doctor_id"])
    if existing and existing["scope"] == req["scope"]:
        expected_expiry = int(time.time()) + int(req["ttl_seconds"])
        if existing["expires_at"] >= expected_expiry - 60:
            access_requests.set_status(user["username"], req_id, "APPROVED")
            flash(f"Dr. {req['doctor_id']} already has this access level.", "info")
            return redirect(url_for("patient.dashboard"))

    policy_store.grant(user["username"], req["doctor_id"], req["scope"], int(req["ttl_seconds"]))
    
    # Record in ledger (since smart contract isn't called directly here, we mimic it or could call it)
    # For simplicity in this demo, we'll just record it via ledger.append_block
    ledger.append_block(
        actor=user["username"], action="GRANT",
        resource=f"patient::{user['username']}",
        details={"doctor": req["doctor_id"], "scope": req["scope"], 
                 "ttl_seconds": req["ttl_seconds"], "via_request": req_id}
    )
    
    access_requests.set_status(user["username"], req_id, "APPROVED")
    
    notifications.push(req["doctor_id"], 
                       f"{user['username']} approved your {req['scope']} access request.",
                       link="/doctor/")
                       
    flash(f"Access granted to Dr. {req['doctor_id']}.", "info")
    return redirect(url_for("patient.dashboard"))


@bp.route("/reject-request", methods=["POST"])
@require_patient
def reject_request():
    user = session["user"]
    req_id = request.form["request_id"]
    req = access_requests.get(user["username"], req_id)
    
    if req:
        access_requests.set_status(user["username"], req_id, "REJECTED")
        notifications.push(req["doctor_id"], 
                           f"{user['username']} declined your access request.",
                           link="/doctor/")
        flash("Access request rejected.", "info")
        
    return redirect(url_for("patient.dashboard"))


@bp.route("/edit", methods=["GET", "POST"])
@require_patient
def edit_profile():
    user = session["user"]
    record = s3_store.get_record(user["username"])
    
    if request.method == "POST":
        record["full_name"] = request.form.get("full_name", "").strip()
        record["dob"] = request.form.get("dob", "").strip()
        record["blood_type"] = request.form.get("blood_type", "").strip()
        record["email"] = request.form.get("email", "").strip()
        
        # Parse allergies
        raw_allergies = request.form.get("allergies_raw", "")
        record["allergies"] = [a.strip() for a in raw_allergies.split(",") if a.strip()]
        
        s3_store.put_record(user["username"], record)
        flash("Profile updated successfully.", "info")
        return redirect(url_for("patient.edit_profile"))

    return render_template("patient_edit.html", user=user, record=record)


@bp.route("/upload-report", methods=["POST"])
@require_patient
def upload_report():
    user = session["user"]
    if "report" not in request.files:
        flash("No file selected", "error")
        return redirect(url_for("patient.edit_profile"))
        
    file = request.files["report"]
    if file.filename == "":
        flash("No file selected", "error")
        return redirect(url_for("patient.edit_profile"))

    # For this demo, we store reports in S3 and record metadata in the EHR JSON
    # In a real app, we'd encrypt the file itself too.
    filename = file.filename
    s3_key = f"reports/{user['username']}/{filename}"
    
    from cloud import config
    config.s3().put_object(
        Bucket=config.S3_BUCKET,
        Key=s3_key,
        Body=file.read(),
        ContentType=file.content_type
    )
    
    record = s3_store.get_record(user["username"])
    record.setdefault("reports", [])
    record["reports"].append({
        "filename": filename,
        "s3_key": s3_key,
        "uploaded_at": datetime.now(timezone.utc).isoformat()
    })
    s3_store.put_record(user["username"], record)
    
    flash(f"Report '{filename}' uploaded successfully.", "info")
    return redirect(url_for("patient.edit_profile"))


@bp.route("/grant", methods=["POST"])
@require_patient
def grant():
    user = session["user"]
    doctor_id = request.form["doctor_id"]
    ttl = int(request.form["ttl_seconds"])
    scope = request.form.get("scope", "read")
    
    # Check if doctor already has access
    existing = policy_store.lookup(user["username"], doctor_id)
    if existing:
        if existing["scope"] == scope:
            # Check if current expiry is far enough in the future (within 1 min tolerance)
            expected_expiry = int(time.time()) + ttl
            if existing["expires_at"] >= expected_expiry - 60:
                flash(f"Dr. {doctor_id} already has active {scope} access with a similar or longer duration.", "info")
                return redirect(url_for("patient.dashboard"))
            else:
                msg = f"Renewed {scope} access for Dr. {doctor_id}."
        else:
            msg = f"Updated Dr. {doctor_id}'s access from {existing['scope']} to {scope}."
    else:
        msg = f"Access granted to Dr. {doctor_id}."

    policy_store.grant(user["username"], doctor_id, scope, ttl)
    
    # Record in ledger via Smart Contract (using token)
    r = call("POST", "grant", user["token"], 
             {"doctor_id": doctor_id, "scope": scope, "ttl_seconds": ttl})
    
    if r["status"] == 200:
        flash(msg, "info")
    else:
        flash(f"Grant failed: {r['body']}", "error")
        
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
