# Threat Model (STRIDE)

Scope: Patient-Centric Healthcare Data Exchange running on the cloud stack
described in [security_cloud_mapping.md](security_cloud_mapping.md).

## Assets
- **A1** Patient EHR (highest sensitivity — HIPAA PHI)
- **A2** Audit ledger (integrity is the security guarantee for the whole system)
- **A3** KMS CMK (compromise = mass decryption)
- **A4** JWT signing key (compromise = identity forgery)
- **A5** Cognito user pool (compromise = login bypass)

## Actors
- **Patient** (owner of their record)
- **Doctor** (consumer; may be honest-but-curious or hostile)
- **Cloud operator** (insider; out of scope but partially mitigated by KMS)
- **External attacker** (no credentials)

## STRIDE per asset

| Asset | Threat | Mitigation (cloud primitive) |
|-------|--------|------------------------------|
| A1 EHR | **Tampering** in S3 | Bucket versioning (S3) + envelope MAC (GCM tag) |
| A1 EHR | **Information disclosure** at rest | SSE-KMS + envelope crypto (defense in depth) |
| A1 EHR | **Information disclosure** in transit | TLS at API Gateway; KMS calls always TLS |
| A2 Ledger | **Tampering** | Chained SHA-256 + verify_chain() + parallel CloudTrail |
| A2 Ledger | **Repudiation** | Every write tagged with JWT subject; DynamoDB streams enable second-source replay |
| A3 KMS CMK | **Elevation of privilege** | IAM policy restricts kms:Decrypt to the smart-contract Lambda role only |
| A3 KMS CMK | **Information disclosure** | Key material never leaves AWS HSM boundary (true on real AWS) |
| A4 JWT key | **Spoofing** (forge tokens) | Stored in Secrets Manager; rotatable; access audited |
| A4 JWT key | **Tampering** | Versioning in Secrets Manager; HMAC-SHA512 verification |
| A5 Cognito | **Spoofing** (credential stuffing) | Cognito password policy + ACCESS_DENIED CloudWatch alarm |
| A5 Cognito | **Denial of service** | API Gateway throttling + WAF rules (production) |

## Out of scope (acknowledged limitations)
- Side-channel attacks against KMS HSMs
- Compromise of the LocalStack runtime itself (lab artifact)
- Browser-side XSS that steals the session JWT — mitigation would be HttpOnly+SameSite cookies (already enabled in Flask defaults)
- Long-term key custody / cryptographic agility (rotation policy is enabled but not exercised here)
