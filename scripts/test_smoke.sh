#!/usr/bin/env bash
set -euo pipefail
: "${APP_NAME:=esri-market-delineation}"
: "${STAGE:=dev}"
API_URL=$(aws cloudformation describe-stacks --stack-name "${APP_NAME}-${STAGE}" --query "Stacks[0].Outputs[?contains(OutputKey, 'ServiceApiEndpoint')].OutputValue" --output text || true)
if [ -z "${API_URL}" ]; then
  API_URL=$(aws cloudformation describe-stack-resources --stack-name "${APP_NAME}-${STAGE}" --query "StackResources[?ResourceType=='AWS::ApiGateway::RestApi'].PhysicalResourceId" --output text)
  API_URL="https://${API_URL}.execute-api.${AWS_REGION}.amazonaws.com/prod"
fi
echo "API: $API_URL"
curl -sS -X POST "$API_URL/market" -H "Content-Type: application/json" -d '{"market_id":"chicago","radius_miles":1}' | jq .
