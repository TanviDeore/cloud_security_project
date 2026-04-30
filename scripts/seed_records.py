"""Loads sample EHRs from data/sample_ehr/*.json into S3 (envelope-encrypted)."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cloud import s3_store

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "sample_ehr")


def main():
    for fname in sorted(os.listdir(DATA_DIR)):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(DATA_DIR, fname)) as f:
            record = json.load(f)
        patient_id = record["patient_id"]
        s3_store.put_record(patient_id, record)
        print(f"Stored {patient_id} ({fname}) -> s3://{os.environ.get('S3_BUCKET','ehr-records')}/patients/{patient_id}.ehr")


if __name__ == "__main__":
    main()
