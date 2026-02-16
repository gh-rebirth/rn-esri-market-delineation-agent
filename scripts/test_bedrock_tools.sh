#!/usr/bin/env bash
set -euo pipefail
: "${AWS_REGION:=us-east-1}"
: "${STAGE:=dev}"
: "${APP_NAME:=esri-market-delineation}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BEDROCK_STACK_NAME="${APP_NAME}-${STAGE}-bedrock-tools"
BASE_STACK_NAME="${APP_NAME}-${STAGE}"
SEED_MARKET_IDS="${SEED_MARKET_IDS:-los_angeles_ca,seattle_wa,boise_id,birmingham_al,miami_fl,baltimore_md,detroit_mi,denver_co,houston_tx,austin_tx,cleveland_oh,boston_ma,nashville_tn,las_vegas_nv,san_francisco_ca,portland_or,tulsa_ok,atlanta_ga,new_york_ny,dallas_tx,chicago_il}"

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

MARKET_IDS_JSON=$(printf '%s\n' "${MARKET_IDS[@]}" | jq -R . | jq -s .)
TOP_K=${TOP_K:-${#MARKET_IDS[@]}}

PROFILE_MARKET=${PROFILE_MARKET:-${MARKET_IDS[0]}}
PROFILE_RESP=$(curl -sS -f -X POST "${BEDROCK_API_BASE}/tools/market-profile" \
  -H "content-type: application/json" \
  -d "{\"market_id\":\"${PROFILE_MARKET}\"}")
echo "${PROFILE_RESP}" | jq .
echo

COMPARE_PAYLOAD=$(jq -n --argjson ids "${MARKET_IDS_JSON}" --argjson top "${TOP_K}" '{market_ids:$ids, top_k:$top}')
COMPARE_RESP=$(curl -sS -f -X POST "${BEDROCK_API_BASE}/tools/market-compare" \
  -H "content-type: application/json" \
  -d "${COMPARE_PAYLOAD}")
echo "${COMPARE_RESP}" | jq .

EXPECTED_COUNT=${#MARKET_IDS[@]}
if [ "${TOP_K}" -lt "${EXPECTED_COUNT}" ]; then
  EXPECTED_COUNT=${TOP_K}
fi
RANKED_COUNT=$(echo "${COMPARE_RESP}" | jq '.ranked | length')
if [ "${RANKED_COUNT}" -lt "${EXPECTED_COUNT}" ]; then
  echo "market-compare returned ${RANKED_COUNT} markets; expected at least ${EXPECTED_COUNT}"
  exit 1
fi

echo
