# Security ↔ Cloud Mapping

This is the slide table that responds directly to the proposal feedback:
*"At least in the design, mention how you can bring in cloud technology."*
Every security control in the system maps to a concrete cloud-native primitive.

| # | Security Requirement | Cloud Service | How it Strengthens the Control |
|---|----------------------|---------------|--------------------------------|
| 1 | Confidentiality of EHR at rest | **S3 + SSE-KMS** with bucket versioning | Server-side encryption is the default; versioning protects against tamper / ransomware rollback |
| 2 | Per-patient key isolation | **AWS KMS** (envelope encryption) | One CMK wraps every per-patient data key; revoking the CMK revokes all decryption ability |
| 3 | Authentication | **Amazon Cognito** user pool | Hosted identity service; pluggable MFA; issues OAuth tokens |
| 4 | Authorization (RBAC) | **IAM-style policy** evaluated in **Lambda** | Declarative JSON policy, identical pattern to real IAM |
| 5 | Tamper-evident audit | **DynamoDB** chained-hash ledger + **CloudTrail** | Two independent records of the same events; chain-break visible in seconds |
| 6 | JWT signing key custody | **AWS Secrets Manager** | Never in code; supports rotation; access is itself audited |
| 7 | Anomaly detection | **CloudWatch Logs** metric filter + alarm | `ACCESS_DENIED` events feed an automated alarm |
| 8 | Reduced compute exposure | **API Gateway** in front of Lambda | No EC2/container surface; throttling and WAF available |
| 9 | Disaster recovery | **S3 versioning** | Point-in-time restore on any object |
| 10 | Least-privilege transport | **VPC endpoints** (production) | Traffic to AWS services never traverses the public internet |

## Why "the cloud version" is stronger than the original SQLite/local design

| Original (proposal) | Cloud (this implementation) | Improvement |
|---------------------|-----------------------------|-------------|
| Local SQLite ledger | DynamoDB (managed, replicated) | Durability + scale |
| Local AES-256 key in code/env | KMS-managed envelope keys | Key never leaves AWS HSM boundary |
| No identity service | Cognito user pools | Centralized identity, pluggable MFA |
| Audit on a single machine | CloudWatch + CloudTrail | Independent, append-only logs |
| Direct Flask exposure | API Gateway → Lambda | Smaller attack surface, throttling |
