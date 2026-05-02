import os
import json
from datetime import datetime, timezone
from cloud import s3_store, ledger

def seed():
    print("Seeding medical data for demo users...")
    
    alice_record = {
        "patient_id": "alice",
        "full_name": "Alice Carter",
        "email": "alice@example.com",
        "dob": "1992-05-14",
        "blood_type": "A+",
        "allergies": ["Peanuts", "Penicillin"],
        "conditions": [
            {"name": "Asthma", "diagnosed": "2010", "status": "active"},
            {"name": "Seasonal Allergies", "diagnosed": "2005", "status": "active"}
        ],
        "medications": [
            {"name": "Albuterol", "dose": "90mcg", "frequency": "As needed"},
            {"name": "Zyrtec", "dose": "10mg", "frequency": "Daily"}
        ],
        "encounters": [
            {"date": "2026-03-10", "provider": "dr_smith", "notes": "Annual physical, all clear."}
        ],
        "clinical_notes": [
            {
                "author": "dr_smith",
                "text": "Patient reports mild wheezing during exercise. Renewed Albuterol inhaler.",
                "created_at": "2026-03-10T14:30:00Z"
            }
        ],
        "reports": [],
        "created_at": "2026-01-01T09:00:00Z"
    }

    bob_record = {
        "patient_id": "bob",
        "full_name": "Bob Nguyen",
        "email": "bob@example.com",
        "dob": "1985-11-22",
        "blood_type": "O-",
        "allergies": ["Sulfa drugs"],
        "conditions": [
            {"name": "Hypertension", "diagnosed": "2020", "status": "active"}
        ],
        "medications": [
            {"name": "Lisinopril", "dose": "10mg", "frequency": "Once daily"}
        ],
        "encounters": [
            {"date": "2026-04-05", "provider": "dr_jones", "notes": "BP check, controlled."}
        ],
        "clinical_notes": [
            {
                "author": "dr_jones",
                "text": "Blood pressure 135/85. Continuing current dosage of Lisinopril.",
                "created_at": "2026-04-05T10:15:00Z"
            }
        ],
        "reports": [],
        "created_at": "2026-01-01T10:00:00Z"
    }

    s3_store.put_record("alice", alice_record)
    print("  seeded alice's record")
    
    s3_store.put_record("bob", bob_record)
    print("  seeded bob's record")

if __name__ == "__main__":
    # Ensure AWS environment variables are set for LocalStack if not already
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
    os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
    os.environ.setdefault("AWS_ENDPOINT_URL", "http://localhost:4566")
    seed()
