#!/usr/bin/env bash
set -euo pipefail

: "${AWS_REGION:=us-east-1}"
: "${STAGE:=dev}"
: "${APP_NAME:=esri-market-delineation}"
: "${LIVE_MARKETS:=atlanta_ga,new_york_ny,dallas_tx,chicago_il}"

STACK_NAME="${APP_NAME}-${STAGE}"
API_URL=$(aws cloudformation describe-stacks \
  --region "$AWS_REGION" \
  --stack-name "$STACK_NAME" \
  --query "Stacks[0].Outputs[?contains(OutputKey, 'ServiceApiEndpoint')].OutputValue | [0]" \
  --output text)

if [ -z "${API_URL}" ] || [ "${API_URL}" = "None" ]; then
  echo "Could not resolve API URL from stack ${STACK_NAME}"
  exit 1
fi

echo "Live pull API: ${API_URL}"
echo "Markets: ${LIVE_MARKETS}"

TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

IFS=',' read -r -a MARKET_IDS <<< "${LIVE_MARKETS}"
for MARKET_ID in "${MARKET_IDS[@]}"; do
  RESP_FILE="${TMP_DIR}/${MARKET_ID}.json"
  curl -sS -f -X POST "${API_URL}/market" \
    -H "content-type: application/json" \
    -d "{\"market_id\":\"${MARKET_ID}\",\"radius_miles\":1,\"force_refresh\":true}" > "${RESP_FILE}"

  jq -e '.data.source == "esri_live"' "${RESP_FILE}" >/dev/null || {
    echo "Live ESRI pull failed for ${MARKET_ID}: expected data.source=esri_live"
    cat "${RESP_FILE}"
    exit 1
  }

  jq -e '.data.totpop > 0 and .data.medhinc > 0' "${RESP_FILE}" >/dev/null || {
    echo "Live ESRI pull failed for ${MARKET_ID}: missing critical values"
    cat "${RESP_FILE}"
    exit 1
  }

  jq -c '[.data.totpop,.data.medhinc,.data.divindx,.data.bachdeg,.data.medage,.data.avghhsz]' "${RESP_FILE}" >> "${TMP_DIR}/tuples.txt"
done

UNIQUE_TUPLES=$(sort -u "${TMP_DIR}/tuples.txt" | wc -l)
if [ "${UNIQUE_TUPLES}" -le 1 ]; then
  echo "Live ESRI pull validation failed: all market feature tuples are identical"
  cat "${TMP_DIR}/tuples.txt"
  exit 1
fi

echo "Live ESRI pull validation passed (${UNIQUE_TUPLES} distinct feature tuples)"
