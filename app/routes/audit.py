"""Audit dashboard: ledger view + chain-verification badge + Matplotlib chart."""
import base64
import io
from collections import Counter
from functools import wraps

from flask import Blueprint, redirect, render_template, session, url_for

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from app.api_gateway_client import call

bp = Blueprint("audit", __name__)


def require_login(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return wrapper


def _build_chart(blocks):
    counts = Counter(b["action"] for b in blocks)
    if not counts:
        return None
    fig, ax = plt.subplots(figsize=(7, 3.5))
    actions = list(counts.keys())
    values = [counts[a] for a in actions]
    colors = ["#2e7d32" if "GRANT" in a or a in ("RECORD_FETCH",) else
              "#c62828" if "DENIED" in a else "#1565c0" for a in actions]
    ax.bar(actions, values, color=colors)
    ax.set_title("Audit Ledger Events by Action")
    ax.set_ylabel("Count")
    plt.xticks(rotation=20, ha="right")
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=110)
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


@bp.route("/")
@require_login
def dashboard():
    user = session["user"]
    audit = call("GET", "audit", user["token"])
    blocks = audit["body"].get("blocks", []) if audit["status"] == 200 else []
    verify = call("GET", "verify-chain", user["token"])
    chain = verify["body"] if verify["status"] == 200 else {"valid": False,
                                                             "reason": verify["body"]}
    chart = _build_chart(blocks)
    return render_template("audit_dashboard.html",
                           user=user, blocks=blocks, chain=chain, chart=chart)
