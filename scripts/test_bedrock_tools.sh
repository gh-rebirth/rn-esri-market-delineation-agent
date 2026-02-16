#!/usr/bin/env bash
set -euo pipefail
: "${AWS_REGION:=us-east-1}"
: "${STAGE:=dev}"
: "${APP_NAME:=esri-market-delineation}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BEDROCK_STACK_NAME="${APP_NAME}-${STAGE}-bedrock-tools"
BASE_STACK_NAME="${APP_NAME}-${STAGE}"
SEED_MARKET_IDS="${SEED_MARKET_IDS:-atlanta_ga,new_york_ny,dallas_tx,chicago_il}"

echo "Running live ESRI pull validation..."
bash "${SCRIPT_DIR}/test_live_pull.sh"

BEDROCK_API_BASE=$(aws cloudformation describe-stacks \
  --region "$AWS_REGION" \
  --stack-name "$BEDROCK_STACK_NAME" \
  --query "Stacks[0].Outputs[?OutputKey=='ApiBaseUrl'].OutputValue" \
  --output text)

MARKET_API_BASE=$(aws cloudformation describe-stacks \
  --region "$AWS_REGION" \
  --stack-name "$BASE_STACK_NAME" \
  --query "Stacks[0].Outputs[?contains(OutputKey, 'ServiceApiEndpoint')].OutputValue | [0]" \
  --output text)

if [ -z "${BEDROCK_API_BASE}" ] || [ "${BEDROCK_API_BASE}" = "None" ]; then
  echo "Could not resolve Bedrock tools API URL from stack ${BEDROCK_STACK_NAME}"
  exit 1
fi

if [ -z "${MARKET_API_BASE}" ] || [ "${MARKET_API_BASE}" = "None" ]; then
  echo "Could not resolve market API URL from stack ${BASE_STACK_NAME}"
  exit 1
fi

echo "Bedrock API: ${BEDROCK_API_BASE}"
echo "Market API:  ${MARKET_API_BASE}"
echo "Seeding markets: ${SEED_MARKET_IDS}"

IFS=',' read -r -a MARKET_IDS <<< "${SEED_MARKET_IDS}"
for MARKET_ID in "${MARKET_IDS[@]}"; do
  curl -sS -f -X POST "${MARKET_API_BASE}/market" \
    -H "content-type: application/json" \
    -d "{\"market_id\":\"${MARKET_ID}\",\"radius_miles\":1,\"include_geometry\":false,\"force_refresh\":true}" >/dev/null
done

curl -sS -X POST "${BEDROCK_API_BASE}/tools/market-profile" -H "content-type: application/json" -d '{"market_id":"atlanta_ga"}'
echo
curl -sS -X POST "${BEDROCK_API_BASE}/tools/market-compare" -H "content-type: application/json" -d '{"market_ids":["atlanta_ga","new_york_ny","dallas_tx","chicago_il"],"top_k":3}'
echo
