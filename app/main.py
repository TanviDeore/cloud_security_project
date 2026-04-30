"""Flask web UI entrypoint."""
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from flask import Flask, redirect, session, url_for

load_dotenv()

from app.routes.auth import bp as auth_bp
from app.routes.patient import bp as patient_bp
from app.routes.doctor import bp as doctor_bp
from app.routes.audit import bp as audit_bp


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret")

    app.register_blueprint(auth_bp)
    app.register_blueprint(patient_bp, url_prefix="/patient")
    app.register_blueprint(doctor_bp, url_prefix="/doctor")
    app.register_blueprint(audit_bp, url_prefix="/audit")

    @app.route("/")
    def index():
        if "user" not in session:
            return redirect(url_for("auth.login"))
        role = session["user"]["role"]
        return redirect(url_for(f"{role}.dashboard"))

    @app.template_filter("ts")
    def fmt_ts(value):
        try:
            dt = datetime.fromisoformat(value)
            return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
        except Exception:
            return value

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(
        host=os.environ.get("FLASK_HOST", "0.0.0.0"),
        port=int(os.environ.get("FLASK_PORT", 5000)),
        debug=True,
    )
