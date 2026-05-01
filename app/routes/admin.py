"""Administrator queue: review pending doctor signups.

The admin role is provisioned out-of-band by infra/seed_users.sh. There is
no /signup/admin route. The admin's sole authority is to authorize NPI
re-verification and approve/reject — every action is recorded in the
tamper-evident ledger.
"""
from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app.api_gateway_client import call
from cloud import users

bp = Blueprint("admin", __name__)


def require_admin(f):
    @wraps(f)
    def wrapper(*a, **kw):
        u = session.get("user")
        if not u or u["role"] != "admin":
            return redirect(url_for("auth.login"))
        return f(*a, **kw)
    return wrapper


@bp.route("/")
@require_admin
def dashboard():
    user = session["user"]
    pending = users.list_by_status("pending_review")
    rejected = users.list_by_status("rejected")
    active_doctors = [u for u in users.list_by_role("doctor")
                      if u.get("status") == "active"]
    return render_template("admin_dashboard.html", user=user,
                           pending=pending, rejected=rejected,
                           active_doctors=active_doctors)


@bp.route("/verify/<username>", methods=["POST"])
@require_admin
def verify(username):
    user = session["user"]
    u = users.get(username) or {}
    r = call("POST", "verify-npi", user["token"], {
        "username": username, "npi": u.get("npi", ""),
        "first_name": u.get("first_name", ""),
        "last_name": u.get("last_name", ""),
        "state": u.get("license_state", ""),
    })
    if r["status"] == 200 and r["body"]["result"].get("valid"):
        flash(f"NPI re-verified for {username} via "
              f"{r['body']['result'].get('source')}.", "info")
    else:
        flash(f"NPI re-check failed: "
              f"{r['body'].get('result', r['body']).get('reason', r['body'])}",
              "error")
    return redirect(url_for("admin.dashboard"))


@bp.route("/approve/<username>", methods=["POST"])
@require_admin
def approve(username):
    user = session["user"]
    r = call("POST", "approve-doctor", user["token"], {"username": username})
    flash(f"Approved {username}." if r["status"] == 200
          else f"Approval failed: {r['body']}",
          "info" if r["status"] == 200 else "error")
    return redirect(url_for("admin.dashboard"))


@bp.route("/reject/<username>", methods=["POST"])
@require_admin
def reject(username):
    user = session["user"]
    reason = request.form.get("reason", "no reason given")
    r = call("POST", "reject-doctor", user["token"],
             {"username": username, "reason": reason})
    flash(f"Rejected {username}." if r["status"] == 200
          else f"Reject failed: {r['body']}",
          "info" if r["status"] == 200 else "error")
    return redirect(url_for("admin.dashboard"))
