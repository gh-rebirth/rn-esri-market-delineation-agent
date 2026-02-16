#!/usr/bin/env bash
set -euo pipefail
: "${APP_NAME:=esri-market-delineation}"
: "${STAGE:=dev}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Running live ESRI pull validation..."
bash "${SCRIPT_DIR}/test_live_pull.sh"

API_URL=$(aws cloudformation describe-stacks --stack-name "${APP_NAME}-${STAGE}" --query "Stacks[0].Outputs[?contains(OutputKey, 'ServiceApiEndpoint')].OutputValue" --output text || true)
if [ -z "${API_URL}" ]; then
  API_URL=$(aws cloudformation describe-stack-resources --stack-name "${APP_NAME}-${STAGE}" --query "StackResources[?ResourceType=='AWS::ApiGateway::RestApi'].PhysicalResourceId" --output text)
  API_URL="https://${API_URL}.execute-api.${AWS_REGION}.amazonaws.com/prod"
fi
echo "API: $API_URL"
SMOKE_RESP=$(curl -sS -X POST "$API_URL/market" -H "Content-Type: application/json" -d '{"market_id":"chicago","radius_miles":1,"force_refresh":true}')
echo "$SMOKE_RESP" | jq .
echo "$SMOKE_RESP" | jq -e '.data.source == "esri_live"' >/dev/null
