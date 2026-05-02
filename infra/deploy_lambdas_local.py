import os
import shutil
import subprocess
import tempfile
import zipfile
import boto3

# Configuration for LocalStack
AWS_ENDPOINT_URL = os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566")
REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
ROLE_ARN = "arn:aws:iam::000000000000:role/lambda-role"

lambda_client = boto3.client(
    "lambda",
    endpoint_url=AWS_ENDPOINT_URL,
    region_name=REGION,
    aws_access_key_id="test",
    aws_secret_access_key="test",
)

def deploy_lambda(name, src_dir):
    print(f"Deploying Lambda: {name} from {src_dir}")
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Copy source files
        shutil.copytree(src_dir, tmp_dir, dirs_exist_ok=True)
        # Copy cloud/ package
        shutil.copytree("cloud", os.path.join(tmp_dir, "cloud"), dirs_exist_ok=True)
        
        # Install requirements
        req_file = os.path.join(src_dir, "requirements.txt")
        if os.path.exists(req_file):
            subprocess.run([
                "pip", "install", "--quiet", "--target", tmp_dir,
                "--platform", "manylinux2014_x86_64",
                "--python-version", "3.11",
                "--implementation", "cp",
                "--only-binary=:all:",
                "--upgrade", "-r", req_file
            ], check=True)
            
        # Create ZIP
        zip_path = os.path.join(tempfile.gettempdir(), f"{name}.zip")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(tmp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, tmp_dir)
                    zipf.write(file_path, arcname)
                    
        with open(zip_path, "rb") as f:
            zip_bytes = f.read()
            
        try:
            lambda_client.get_function(FunctionName=name)
            lambda_client.update_function_code(
                FunctionName=name,
                ZipFile=zip_bytes
            )
            print(f"Updated Lambda {name}")
        except lambda_client.exceptions.ResourceNotFoundException:
            lambda_client.create_function(
                FunctionName=name,
                Runtime="python3.11",
                Role=ROLE_ARN,
                Handler="handler.lambda_handler",
                Code={"ZipFile": zip_bytes},
                Timeout=15,
                Environment={
                    "Variables": {
                        "AWS_ENDPOINT_URL": "http://localstack:4566",
                        "KMS_KEY_ALIAS": os.environ.get("KMS_KEY_ALIAS", "alias/ehr-cmk"),
                        "S3_BUCKET": os.environ.get("S3_BUCKET", "ehr-records"),
                        "DDB_LEDGER_TABLE": os.environ.get("DDB_LEDGER_TABLE", "AuditLedger"),
                        "DDB_POLICY_TABLE": os.environ.get("DDB_POLICY_TABLE", "AccessPolicies"),
                        "SECRET_NAME": os.environ.get("SECRET_NAME", "ehr/jwt-signing-key"),
                        "LOG_GROUP": os.environ.get("LOG_GROUP", "/ehr/app"),
                    }
                }
            )
            print(f"Created Lambda {name}")

if __name__ == "__main__":
    deploy_lambda("ehr-smart-contract", "lambdas/smart_contract")
    deploy_lambda("ehr-audit-appender", "lambdas/audit_appender")
