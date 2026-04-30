# Recorded Presentation — Walkthrough Script (8–10 min)

Submission: per professor's email, place this MP4 plus the .pptx into a
subfolder named "Vaish-Deore_EHR-Blockchain-Cloud" and upload to the TA folder
on Teams.

## Pre-recording checklist
- [ ] `docker compose up -d` — wait for `localstack` healthy
- [ ] `bash infra/bootstrap.sh` — KMS, S3, DynamoDB, Cognito, Secrets, Lambda, API GW, CloudWatch
- [ ] `python scripts/seed_records.py` — encrypts Alice + Bob into S3
- [ ] `python -m app.main` — Flask UI on http://localhost:5000
- [ ] Open three terminals: (1) Flask logs, (2) demo scripts, (3) `awslocal logs tail /ehr/app --follow`

## Slide outline (.pptx)
1. **Title** — Patient-Centric EHR Exchange · Cloud + Blockchain Audit
2. **Problem** — patient does not own their record; cross-institution access is opaque
3. **Threat model** — STRIDE table from `threat_model.md`
4. **Architecture** — `architecture.png`; voiceover: "every box is a managed cloud service"
5. **Security ↔ Cloud mapping** — table from `security_cloud_mapping.md` (this is the slide that answers the proposal feedback)
6. **Live demo intro** — 3 scenarios coming up
7. **Tamper detection** — screenshot of the red CHAIN BROKEN badge
8. **Limitations + future work** — multi-region KMS, real Cognito hosted UI, Macie scan on bucket
9. **Q&A**

## Demo segments

### Segment A · Happy path (~2 min)
1. Browser → http://localhost:5000 → log in as **alice / password**
2. Patient dashboard. Voiceover: "Alice is the sole authority over her record."
3. Grant `dr_smith` 24h read access. Show the ledger entry appear in the patient view.
4. Logout. Log in as **dr_smith / password**.
5. Doctor dashboard → request `alice`'s record. Show the decrypted JSON. Voiceover: "S3 returned ciphertext; KMS unwrapped the data key; Lambda decrypted in memory."
6. Open Audit tab. Show CHAIN VALID badge + Matplotlib chart.

### Segment B · Denied access + alarm (~2 min)
1. Switch terminal 2 → `python scripts/demo_denied_access.py`
2. Narrate as it runs: dr_jones denied (no grant); Alice revokes dr_smith; dr_smith's retry denied.
3. Script ends by hammering the API to trip `EHR-AccessDenied-Burst` alarm.
4. Show the alarm state transitioning to `ALARM`.
5. Show terminal 3 (CloudWatch Logs tail) to prove ACCESS_DENIED events flowed.

### Segment C · Tamper detection (~2 min) — the headline moment
1. Terminal 2 → `python scripts/demo_tamper_detection.py`
2. Narrate: "I'm reaching directly into DynamoDB, behind the application, to edit a block in place."
3. Show `verify_chain` returning `valid: false` with the broken block_id.
4. Switch back to browser → /audit → giant red CHAIN BROKEN badge pulsing.
5. Voiceover: "This is what makes the audit trail trustworthy. Even an insider with database access cannot rewrite history without leaving a visible break."
6. Script restores the block; show the badge return to green.

### Segment D · Wrap (~1 min)
- Re-open the security ↔ cloud mapping slide.
- One-line takeaway per row.
- Final slide: "Patient-controlled access · cloud-native cryptography · independent audit · automated detection."

## Recording tips
- 1080p, system audio + mic.
- Bump terminal font size to ~16pt and browser zoom to 110%.
- Mute notifications; close unrelated apps.
- One take per segment is fine — concatenate in iMovie / QuickTime.
