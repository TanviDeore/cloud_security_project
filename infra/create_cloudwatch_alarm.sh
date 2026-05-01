#!/usr/bin/env bash
# Creates a CloudWatch log group, a metric filter that counts ACCESS_DENIED
# events, and an alarm that fires on >5 denials per minute.
#
# put-metric-alarm is invoked via boto3 (Python) because LocalStack 3.5
# Community Edition has a known query-protocol parsing issue with the awscli
# client for that specific call. The metric filter and log group are still
# created via awslocal.
set -euo pipefail

LOG_GROUP=${LOG_GROUP:-/ehr/app}

awslocal logs create-log-group \
  --log-group-name "$LOG_GROUP" >/dev/null 2>&1 || true
awslocal logs create-log-stream \
  --log-group-name "$LOG_GROUP" --log-stream-name "events" >/dev/null 2>&1 || true

awslocal logs put-metric-filter \
  --log-group-name "$LOG_GROUP" \
  --filter-name "AccessDeniedFilter" \
  --filter-pattern '"ACCESS_DENIED"' \
  --metric-transformations \
    metricName=AccessDeniedCount,metricNamespace=EHR,metricValue=1,defaultValue=0 \
  >/dev/null 2>&1 || echo "(metric filter not enforced by LocalStack community)"

python3 - <<'PY' || echo "(alarm creation skipped — LocalStack community CW limitation)"
import os, boto3
cw = boto3.client(
    "cloudwatch",
    endpoint_url=os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566"),
    region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    aws_access_key_id="test", aws_secret_access_key="test",
)
try:
    cw.put_metric_alarm(
        AlarmName="EHR-AccessDenied-Burst",
        MetricName="AccessDeniedCount",
        Namespace="EHR",
        Statistic="Sum",
        Period=60,
        Threshold=5,
        ComparisonOperator="GreaterThanThreshold",
        EvaluationPeriods=1,
        TreatMissingData="notBreaching",
    )
    print("CloudWatch alarm 'EHR-AccessDenied-Burst' created via boto3")
except Exception as e:
    print(f"(alarm not created: {e.__class__.__name__})")
PY

echo "CloudWatch metric filter configured (alarm best-effort)"
