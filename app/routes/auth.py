"""Login/logout. After Cognito auth we mint a short-lived HS512 JWT signed
with the Secrets Manager key — the smart-contract Lambda verifies that JWT.
"""
import time

import jwt as pyjwt
from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from cloud import cognito_client, cloudwatch_logger
from cloud.secrets_client import jwt_signing_key

bp = Blueprint("auth", __name__)


def issue_jwt(username: str, role: str, ttl: int = 3600) -> str:
    now = int(time.time())
    payload = {"sub": username, "role": role, "iat": now, "exp": now + ttl}
    return pyjwt.encode(payload, jwt_signing_key(), algorithm="HS512")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        result = cognito_client.login(username, password)
        if not result:
            cloudwatch_logger.emit("LOGIN_FAILED", actor=username)
            flash("Invalid credentials", "error")
            return render_template("login.html"), 401
        token = issue_jwt(result["username"], result["role"])
        session["user"] = {
            "username": result["username"],
            "role": result["role"],
            "token": token,
        }
        cloudwatch_logger.emit("LOGIN_OK", actor=username, role=result["role"])
        return redirect(url_for("index"))
    return render_template("login.html")


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
