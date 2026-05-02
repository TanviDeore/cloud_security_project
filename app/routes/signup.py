"""Self-service registration.

* /signup           — patients self-register, status=active, empty EHR seeded
* /signup/doctor    — doctors register with NPI + license state. NPI is
                      verified against the live CMS registry; on match the
                      account is auto-approved, otherwise it goes to the
                      admin queue.
"""
import re
import time
from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for

from cloud import cloudwatch_logger, ledger, notifications, npi_client, \
    passwords, s3_store, users

bp = Blueprint("signup", __name__)

USERNAME_RE = re.compile(r"^[a-z0-9_]{3,32}$")


def _validate_password(pw: str) -> str:
    if len(pw) < 8:
        return "Password must be at least 8 characters"
    if pw.lower() == pw:
        return "Password must include at least one uppercase letter"
    if not re.search(r"\d", pw):
        return "Password must include at least one digit"
    return ""


def _validate_username(name: str) -> str:
    if not USERNAME_RE.fullmatch(name):
        return "Username must be 3–32 chars, lowercase letters/digits/_ only"
    if users.get(name):
        return "Username already taken"
    return ""


@bp.route("/signup", methods=["GET", "POST"])
def patient_signup():
    if request.method == "POST":
        u = request.form["username"].strip().lower()
        email = request.form.get("email", "").strip()
        full = request.form.get("full_name", "").strip()
        pw = request.form["password"]
        err = _validate_username(u) or _validate_password(pw)
        if err:
            flash(err, "error")
            return render_template("signup_patient.html",
                                   form=request.form), 400
        users.put({
            "username": u, "email": email, "role": "patient",
            "status": "active",
            "password_hash": passwords.hash_password(pw),
            "created_at": int(time.time()),
            "failed_attempts": 0, "locked_until": 0,
            "full_name": full,
        })
        s3_store.put_record(u, s3_store.empty_initial_record(u, full, email))
        ledger.append_block(actor=u, action="SIGNUP",
                            resource=f"user::{u}",
                            details={"role": "patient"})
        notifications.push(u, "Welcome — your encrypted record has been "
                              "provisioned in S3.", link="/patient/")
        cloudwatch_logger.emit("SIGNUP", actor=u, role="patient")
        flash("Account created. You can now sign in.", "info")
        return redirect(url_for("auth.login"))
    return render_template("signup_patient.html", form={})


@bp.route("/signup/doctor", methods=["GET", "POST"])
def doctor_signup():
    if request.method == "POST":
        u = request.form["username"].strip().lower()
        email = request.form.get("email", "").strip()
        first = request.form["first_name"].strip()
        last = request.form["last_name"].strip()
        npi = request.form["npi"].strip()
        state = request.form.get("license_state", "").strip().upper()
        pw = request.form["password"]
        err = _validate_username(u) or _validate_password(pw)
        if err:
            flash(err, "error")
            return render_template("signup_doctor.html",
                                   form=request.form), 400

        verification = npi_client.verify(npi, first, last, state)
        status = "active" if verification.get("valid") else "pending_review"

        users.put({
            "username": u, "email": email, "role": "doctor", "status": status,
            "password_hash": passwords.hash_password(pw),
            "created_at": int(time.time()),
            "failed_attempts": 0, "locked_until": 0,
            "first_name": first, "last_name": last,
            "npi": npi, "license_state": state,
            "npi_verified": bool(verification.get("valid")),
            "npi_source": verification.get("source", ""),
            "npi_reason": verification.get("reason", ""),
        })

        action = "NPI_VERIFIED" if verification.get("valid") else "NPI_REVIEW_NEEDED"
        ledger.append_block(actor=u, action=action,
                            resource=f"user::{u}",
                            details={"npi": npi,
                                     "source": verification.get("source"),
                                     "reason": verification.get("reason", "")})
        cloudwatch_logger.emit(action, actor=u, npi=npi,
                               valid=bool(verification.get("valid")))

        if verification.get("valid"):
            notifications.push(u, f"NPI {npi} verified ({verification['source']}). "
                                  "You may now sign in.", link="/login")
            flash(f"NPI verified via {verification['source']}. "
                  "You can sign in now.", "info")
        else:
            for admin_user in users.list_by_role("admin"):
                notifications.push(admin_user["username"],
                                   f"New doctor signup awaiting review: {u}",
                                   link="/admin/")
            flash("Your account is pending administrator review.", "info")
        return redirect(url_for("auth.login"))
    return render_template("signup_doctor.html", form={})
