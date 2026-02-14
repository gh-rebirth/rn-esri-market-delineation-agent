
# Deployment Quickstart (AWS CDK)

## Required environment variables

```bash
export AWS_PROFILE=<your-profile>
export AWS_REGION=us-east-1
export STAGE=dev
export APP_NAME=esri-market-delineation
```

## Deploy

```bash
bash scripts/deploy_codex.sh
```

## Outputs

The deploy script prints:
- API Gateway URL
- DynamoDB table names
- SQS queue URL
- Lambda function names

## Test endpoint

```bash
API_URL="<api-base-url>"
curl -sS -X POST "${API_URL}/market"   -H "Content-Type: application/json"   -d '{"market_id":"chicago_il","lat":41.8781,"lon":-87.6298,"radius_miles":1,"include_geometry":false}' | jq
```

## Notes for Codex CLI
- Codex should prefer `scripts/deploy_codex.sh` and `scripts/test_smoke.sh`.
- If tests fail, Codex should patch minimally and re-run.
- Never print or commit plaintext secrets.
