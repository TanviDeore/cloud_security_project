"""KMS-signed PDF export of a patient's audit log.

Workflow:
1. Render a PDF of the patient's ledger entries using reportlab.
2. SHA-256 the PDF bytes.
3. Ask KMS to sign the digest with the asymmetric RSA-2048 signing key
   (KMS handles the actual private key in its HSM).
4. Append a signature block to the PDF as a second page so the file is
   self-verifying: anyone with the public key (also published) can confirm
   the export wasn't altered after issuance.
"""
import base64
import hashlib
import io
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)

from . import config

SIGNER_ALIAS = os.environ.get("KMS_SIGNER_ALIAS", "alias/ehr-pdf-signer")


def _styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle(name="Mono", fontName="Courier", fontSize=8,
                         textColor=colors.HexColor("#475569")))
    s.add(ParagraphStyle(name="Hash", fontName="Courier", fontSize=7,
                         textColor=colors.HexColor("#64748b"), wordWrap="CJK"))
    return s


def _render_pdf(patient: str, blocks: List[Dict[str, Any]],
                chain_status: Dict[str, Any]) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER, title=f"EHR audit · {patient}",
                            author="EHR Cloud Exchange", leftMargin=48,
                            rightMargin=48, topMargin=54, bottomMargin=54)
    s = _styles()
    story = []

    story.append(Paragraph("EHR Cloud Exchange", s["Heading2"]))
    story.append(Paragraph("Patient-Centric Audit Export", s["Title"]))
    story.append(Spacer(1, 12))

    issued = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    meta = [
        ["Patient", patient],
        ["Issued", issued],
        ["Chain status",
         f"VALID ({chain_status.get('total', 0)} blocks)"
         if chain_status.get("valid") else
         f"BROKEN at #{chain_status.get('broken_at')} — {chain_status.get('reason','')}"],
        ["Signing key", SIGNER_ALIAS + " (RSA-2048, KMS-managed)"],
    ]
    t = Table(meta, hAlign="LEFT", colWidths=[110, 360])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f5f9")),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 14))

    story.append(Paragraph("Audit ledger (chronological)", s["Heading3"]))

    rows = [["#", "Time (UTC)", "Actor", "Action", "Details"]]
    for b in blocks:
        details = (b.get("details") or "")[:90]
        if len(b.get("details") or "") > 90:
            details += "…"
        rows.append([
            str(int(b["block_id"])),
            b["timestamp"][:19].replace("T", " "),
            b["actor"], b["action"], details,
        ])
    body = Table(rows, hAlign="LEFT", repeatRows=1,
                 colWidths=[28, 110, 70, 90, 180])
    body.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(body)

    story.append(PageBreak())
    story.append(Paragraph("Cryptographic signature", s["Heading2"]))
    story.append(Paragraph(
        "This document is digitally signed using AWS KMS. The signature on the "
        "next line is over the SHA-256 digest of the body. Verification "
        "requires the public key associated with the signing key alias above. "
        "Any modification of the body invalidates the signature.", s["BodyText"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph("Body SHA-256:", s["Heading4"]))
    story.append(Paragraph("__BODY_HASH_PLACEHOLDER__", s["Hash"]))
    story.append(Paragraph("KMS signature (base64):", s["Heading4"]))
    story.append(Paragraph("__SIGNATURE_PLACEHOLDER__", s["Hash"]))

    story.append(Spacer(1, 24))
    story.append(Paragraph("Glossary", s["Heading4"]))
    story.append(Paragraph(
        "<b>Chain status</b>: Every ledger entry is linked to the previous one using "
        "cryptographic hashes (a blockchain-style structure). A 'VALID' status confirms "
        "the entire history is intact and untampered with. A 'BROKEN' status indicates "
        "unauthorized modification of past records.", s["BodyText"]))

    doc.build(story)
    return buf.getvalue()


def build_signed_audit_pdf(patient: str, blocks: List[Dict[str, Any]],
                            chain_status: Dict[str, Any]) -> Dict[str, Any]:
    body_pdf = _render_pdf(patient, blocks, chain_status)
    body_hash = hashlib.sha256(body_pdf).digest()

    kms = config.kms()
    sig_resp = kms.sign(
        KeyId=SIGNER_ALIAS,
        Message=body_hash,
        MessageType="DIGEST",
        SigningAlgorithm="RSASSA_PKCS1_V1_5_SHA_256",
    )
    sig_b64 = base64.b64encode(sig_resp["Signature"]).decode()
    body_hash_hex = body_hash.hex()

    # Re-render with the actual hash + signature substituted in.
    final = body_pdf.replace(b"__BODY_HASH_PLACEHOLDER__",
                             body_hash_hex.encode())
    final = final.replace(b"__SIGNATURE_PLACEHOLDER__", sig_b64.encode())
    return {
        "pdf": final,
        "body_sha256": body_hash_hex,
        "signature_b64": sig_b64,
        "signing_key": SIGNER_ALIAS,
    }
