"""Notification inbox."""
from functools import wraps

from flask import Blueprint, redirect, render_template, session, url_for

from cloud import notifications

bp = Blueprint("notifs", __name__)


def require_login(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if "user" not in session:
            return redirect(url_for("auth.login"))
        return f(*a, **kw)
    return wrapper


@bp.route("/")
@require_login
def inbox():
    user = session["user"]
    items = notifications.list_for(user["username"], limit=100)
    notifications.mark_all_read(user["username"])
    return render_template("notifications.html", user=user, items=items)
