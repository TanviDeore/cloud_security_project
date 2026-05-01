"""Audit dashboard: ledger view + chain-verification badge + Matplotlib chart
+ KMS-signed PDF export for the patient."""
import base64
import io
from collections import Counter
from functools import wraps

from flask import (Blueprint, redirect, render_template, send_file, session,
                   url_for)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from app.api_gateway_client import call
from cloud import pdf_signer

bp = Blueprint("audit", __name__)


def require_login(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if "user" not in session:
            return redirect(url_for("auth.login"))
        return f(*a, **kw)
    return wrapper


def _build_chart(blocks):
    counts = Counter(b["action"] for b in blocks)
    if not counts:
        return None

    BG       = "#161a26"   # matches --surface-2 in style.css
    GRID     = "#2a3041"
    INK      = "#e8eaf0"
    INK_SOFT = "#9ba3b4"

    fig, ax = plt.subplots(figsize=(7, 3.5), facecolor=BG)
    ax.set_facecolor(BG)
    actions = list(counts.keys())
    values = [counts[a] for a in actions]
    colors = []
    for a in actions:
        if "DENIED" in a or a == "REJECT_DOCTOR":
            colors.append("#f87171")
        elif a in ("GRANT", "RECORD_FETCH", "APPROVE_DOCTOR", "NPI_VERIFIED"):
            colors.append("#4ade80")
        elif a == "UPDATE_RECORD":
            colors.append("#fbbf24")
        else:
            colors.append("#818cf8")
    ax.bar(actions, values, color=colors)
    ax.set_title("Audit Ledger Events by Action", color=INK,
                 fontsize=11, pad=10)
    ax.set_ylabel("Count", color=INK_SOFT)
    ax.tick_params(colors=INK_SOFT)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("bottom", "left"):
        ax.spines[spine].set_color(GRID)
    ax.yaxis.grid(True, color=GRID, linewidth=0.5)
    ax.set_axisbelow(True)
    plt.xticks(rotation=20, ha="right")
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=110, facecolor=BG)
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


@bp.route("/")
@require_login
def dashboard():
    user = session["user"]
    audit = call("GET", "audit", user["token"])
    blocks = audit["body"].get("blocks", []) if audit["status"] == 200 else []
    verify = call("GET", "verify-chain", user["token"])
    chain = verify["body"] if verify["status"] == 200 else {
        "valid": False, "reason": verify["body"]}
    chart = _build_chart(blocks)
    return render_template("audit_dashboard.html", user=user,
                           blocks=blocks, chain=chain, chart=chart)


@bp.route("/export.pdf")
@require_login
def export_pdf():
    user = session["user"]
    audit = call("GET", "audit", user["token"])
    blocks = audit["body"].get("blocks", []) if audit["status"] == 200 else []
    verify = call("GET", "verify-chain", user["token"])
    chain = verify["body"] if verify["status"] == 200 else {"valid": False}
    out = pdf_signer.build_signed_audit_pdf(user["username"], blocks, chain)
    return send_file(io.BytesIO(out["pdf"]),
                     mimetype="application/pdf",
                     as_attachment=True,
                     download_name=f"ehr-audit-{user['username']}.pdf")
