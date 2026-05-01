"""Flask web UI entrypoint."""
import json
import os
import time
from datetime import datetime, timezone

from dotenv import load_dotenv
from flask import Flask, redirect, render_template, session, url_for

load_dotenv()

from app.routes.admin import bp as admin_bp
from app.routes.auth import bp as auth_bp
from app.routes.audit import bp as audit_bp
from app.routes.doctor import bp as doctor_bp
from app.routes.notifs import bp as notifs_bp
from app.routes.patient import bp as patient_bp
from app.routes.signup import bp as signup_bp
from cloud import notifications


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret")
    # Pick up template edits without restarting the server
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.jinja_env.auto_reload = True

    app.register_blueprint(auth_bp)
    app.register_blueprint(signup_bp)
    app.register_blueprint(patient_bp, url_prefix="/patient")
    app.register_blueprint(doctor_bp, url_prefix="/doctor")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(audit_bp, url_prefix="/audit")
    app.register_blueprint(notifs_bp, url_prefix="/notifications")

    @app.route("/")
    def index():
        if "user" not in session:
            return redirect(url_for("auth.login"))
        role = session["user"]["role"]
        if role == "admin":
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for(f"{role}.dashboard"))

    @app.route("/cloud-architecture")
    def cloud_architecture():
        return render_template("cloud_architecture.html")

    @app.context_processor
    def inject_notifs():
        u = session.get("user")
        if not u:
            return {}
        try:
            return {"unread_count": notifications.unread_count(u["username"])}
        except Exception:
            return {"unread_count": 0}

    @app.template_filter("ts")
    def fmt_ts(value):
        try:
            dt = datetime.fromisoformat(value)
            return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            return value

    @app.template_filter("utc_dt")
    def utc_dt(epoch):
        try:
            dt = datetime.fromtimestamp(int(epoch), tz=timezone.utc)
            return dt.strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            return ""

    @app.template_filter("notif_dt")
    def notif_dt(notif_id):
        try:
            ts_ms = int(str(notif_id)[:13])
            dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
            return dt.strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            return ""

    @app.template_filter("relative_time")
    def relative_time(epoch):
        try:
            diff = int(epoch) - int(time.time())
        except Exception:
            return ""
        if diff <= 0:
            return "expired"
        days = diff // 86400
        hours = (diff % 86400) // 3600
        minutes = (diff % 3600) // 60
        parts = []
        if days:    parts.append(f"{days}d")
        if hours:   parts.append(f"{hours}h")
        if not days and minutes:
            parts.append(f"{minutes}m")
        return " ".join(parts) if parts else "<1m"

    @app.template_filter("format_details")
    def format_details(block):
        """Render an audit block's details JSON as a human-readable line."""
        try:
            d = json.loads(block.get("details") or "{}")
        except Exception:
            return ""
        action = block.get("action", "")
        if action == "GRANT":
            scope = d.get("scope", "?")
            ttl = int(d.get("ttl_seconds", 0))
            human = _ttl_human(ttl)
            return f"granted {scope} access for {human}"
        if action == "REVOKE":
            return "access revoked"
        if action == "RECORD_FETCH":
            return f"viewed record · scope: {d.get('scope', '?')}"
        if action == "UPDATE_RECORD":
            note = (d.get("note_excerpt") or "").strip()
            if len(note) > 90:
                note = note[:87] + "…"
            return f"added clinical note · {note}" if note else "added clinical note"
        if action == "ACCESS_DENIED":
            return f"denied: {d.get('reason', 'unauthorized')}"
        if action == "APPROVE_DOCTOR":
            return f"approved by {d.get('approved_by', 'admin')}"
        if action == "REJECT_DOCTOR":
            return f"rejected: {d.get('reason', '')}"
        if action == "NPI_VERIFIED":
            return f"NPI verified ({d.get('source', 'registry')})"
        if action == "NPI_REVIEW_NEEDED":
            return f"NPI review needed: {d.get('reason', '')}"
        if action == "SIGNUP":
            return f"new {d.get('role', 'user')} account"
        return ""

    return app


def _ttl_human(ttl_seconds: int) -> str:
    if ttl_seconds <= 0:
        return "—"
    days = ttl_seconds // 86400
    hours = (ttl_seconds % 86400) // 3600
    if days and hours:
        return f"{days}d {hours}h"
    if days:
        return f"{days}d"
    if hours:
        return f"{hours}h"
    return f"{ttl_seconds // 60}m"


if __name__ == "__main__":
    app = create_app()
    debug = os.environ.get("FLASK_DEBUG", "1") not in ("0", "false", "False")
    app.run(
        host=os.environ.get("FLASK_HOST", "0.0.0.0"),
        port=int(os.environ.get("FLASK_PORT", 5000)),
        debug=debug,
        use_reloader=False,
    )
