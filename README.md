# Patient-Centric Healthcare Data Exchange (Cloud + Blockchain Audit)

Course project for *Special Topics: Secure Cloud / Edge / IoT* (Spring 2026).

A patient-controlled EHR sharing platform where every security control maps to a
cloud-native primitive. Blockchain-style audit trail (chained SHA-256) lives in
DynamoDB; patient records live AES-encrypted in S3 with KMS envelope keys; access
control is enforced by a smart-contract Lambda fronted by API Gateway. Everything
runs locally on **LocalStack** so it costs nothing, but uses the same AWS APIs a
production deployment would.

## Security ↔ Cloud Mapping

| Security requirement              | Cloud service                                    |
| --------------------------------- | ------------------------------------------------ |
| EHR confidentiality at rest       | S3 + SSE-KMS, bucket versioning                  |
| Per-patient key isolation         | KMS envelope encryption (CMK + data keys)        |
| JWT signing key storage           | Secrets Manager                                  |
| AuthN (patient / doctor login)    | Cognito user pool                                |
| AuthZ / RBAC                      | IAM-style policy doc evaluated in Lambda         |
| Tamper-evident audit              | DynamoDB chained-hash ledger + CloudTrail mirror |
| Anomaly detection                 | CloudWatch Logs metric filter + alarm            |
| Reduced compute exposure          | API Gateway in front of Lambda                   |
| Disaster recovery                 | S3 versioning                                    |

## Quickstart

```bash
# 1. Boot LocalStack
docker compose up -d
# wait until healthy:
curl -s http://localhost:4566/_localstack/health | grep '"running"'

# 2. Python env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# 3. Provision all "AWS" resources in LocalStack
bash infra/bootstrap.sh

# 4. Run the Flask UI
python -m app.main
# open http://localhost:5000
```

## Demo scripts

```bash
python scripts/demo_happy_path.py        # grant -> fetch -> ledger entry
python scripts/demo_denied_access.py     # no grant -> denied -> CloudWatch alarm
python scripts/demo_tamper_detection.py  # corrupt a block -> verify_chain fails
```

## Repository layout

See [docs/architecture.png](docs/architecture.png) and the file tree in the
project plan. Top-level packages:

- `infra/` – LocalStack bootstrap scripts (S3, KMS, DynamoDB, Cognito, Lambda, API Gateway, CloudWatch)
- `cloud/` – boto3 wrappers; the entire cloud surface lives here
- `lambdas/` – deploy-ready smart-contract + audit-appender functions
- `app/`    – Flask web UI (talks only to API Gateway)
- `scripts/`– demo scripts driven during the recorded presentation
- `tests/`  – pytest suite for chain integrity, crypto, RBAC, end-to-end
- `docs/`   – diagrams, threat model, security↔cloud mapping, demo script
