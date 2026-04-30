#!/usr/bin/env bash
# Creates a REST API Gateway in front of the smart-contract Lambda.
# Routes:
#   POST /grant   POST /revoke   POST /request-record   GET /audit
set -euo pipefail

API_NAME=${API_GATEWAY_NAME:-ehr-api}
LAMBDA=${LAMBDA_SMART_CONTRACT:-ehr-smart-contract}
REGION=${AWS_DEFAULT_REGION:-us-east-1}

ROOT="$(cd "$(dirname "$0")"/.. && pwd)"

# Reuse if exists
EXISTING=$(aws --endpoint-url "$AWS_ENDPOINT_URL" apigateway get-rest-apis \
  --query "items[?name=='${API_NAME}'].id" --output text || true)
if [ -n "$EXISTING" ] && [ "$EXISTING" != "None" ]; then
  API_ID="$EXISTING"
  echo "API Gateway $API_NAME exists ($API_ID)"
else
  API_ID=$(aws --endpoint-url "$AWS_ENDPOINT_URL" apigateway create-rest-api \
    --name "$API_NAME" --query 'id' --output text)
  echo "Created API Gateway $API_NAME ($API_ID)"
fi

ROOT_ID=$(aws --endpoint-url "$AWS_ENDPOINT_URL" apigateway get-resources \
  --rest-api-id "$API_ID" --query "items[?path=='/'].id" --output text)

LAMBDA_ARN=$(aws --endpoint-url "$AWS_ENDPOINT_URL" lambda get-function \
  --function-name "$LAMBDA" --query 'Configuration.FunctionArn' --output text)
INVOKE_URI="arn:aws:apigateway:${REGION}:lambda:path/2015-03-31/functions/${LAMBDA_ARN}/invocations"

create_route() {
  local PATH_PART=$1; local METHOD=$2
  local RID
  RID=$(aws --endpoint-url "$AWS_ENDPOINT_URL" apigateway get-resources \
    --rest-api-id "$API_ID" --query "items[?pathPart=='${PATH_PART}'].id" --output text)
  if [ -z "$RID" ] || [ "$RID" = "None" ]; then
    RID=$(aws --endpoint-url "$AWS_ENDPOINT_URL" apigateway create-resource \
      --rest-api-id "$API_ID" --parent-id "$ROOT_ID" --path-part "$PATH_PART" \
      --query 'id' --output text)
  fi
  aws --endpoint-url "$AWS_ENDPOINT_URL" apigateway put-method \
    --rest-api-id "$API_ID" --resource-id "$RID" \
    --http-method "$METHOD" --authorization-type NONE >/dev/null 2>&1 || true
  aws --endpoint-url "$AWS_ENDPOINT_URL" apigateway put-integration \
    --rest-api-id "$API_ID" --resource-id "$RID" \
    --http-method "$METHOD" --type AWS_PROXY \
    --integration-http-method POST \
    --uri "$INVOKE_URI" >/dev/null
  echo "  $METHOD /$PATH_PART -> $LAMBDA"
}

create_route "grant"          POST
create_route "revoke"         POST
create_route "request-record" POST
create_route "audit"          GET
create_route "verify-chain"   GET

aws --endpoint-url "$AWS_ENDPOINT_URL" apigateway create-deployment \
  --rest-api-id "$API_ID" --stage-name dev >/dev/null

# Allow API Gateway to invoke the Lambda
aws --endpoint-url "$AWS_ENDPOINT_URL" lambda add-permission \
  --function-name "$LAMBDA" \
  --statement-id "apigw-invoke" \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:${REGION}:000000000000:${API_ID}/*/*" \
  >/dev/null 2>&1 || true

mkdir -p "$ROOT/.localstack"
echo "{\"api_id\":\"$API_ID\",\"base_url\":\"http://localhost:4566/restapis/$API_ID/dev/_user_request_\"}" \
  > "$ROOT/.localstack/api_gateway.json"
echo "API base: http://localhost:4566/restapis/$API_ID/dev/_user_request_"
