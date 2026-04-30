#!/usr/bin/env bash
# Creates a CloudWatch log group, a metric filter that counts ACCESS_DENIED
# events, and an alarm that fires on >5 denials per minute.
set -euo pipefail

LOG_GROUP=${LOG_GROUP:-/ehr/app}

aws --endpoint-url "$AWS_ENDPOINT_URL" logs create-log-group \
  --log-group-name "$LOG_GROUP" >/dev/null 2>&1 || true
aws --endpoint-url "$AWS_ENDPOINT_URL" logs create-log-stream \
  --log-group-name "$LOG_GROUP" --log-stream-name "events" >/dev/null 2>&1 || true

aws --endpoint-url "$AWS_ENDPOINT_URL" logs put-metric-filter \
  --log-group-name "$LOG_GROUP" \
  --filter-name "AccessDeniedFilter" \
  --filter-pattern '"ACCESS_DENIED"' \
  --metric-transformations \
    metricName=AccessDeniedCount,metricNamespace=EHR,metricValue=1,defaultValue=0 \
  >/dev/null

aws --endpoint-url "$AWS_ENDPOINT_URL" cloudwatch put-metric-alarm \
  --alarm-name "EHR-AccessDenied-Burst" \
  --metric-name AccessDeniedCount \
  --namespace EHR \
  --statistic Sum \
  --period 60 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --treat-missing-data notBreaching \
  >/dev/null

echo "CloudWatch metric filter + alarm 'EHR-AccessDenied-Burst' configured"
