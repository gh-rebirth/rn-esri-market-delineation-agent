# ESRI Market Delineation on AWS (Combined Package)

This repo deploys a low-latency market delineation service on AWS with:
- API Lambda for online lookups
- DynamoDB cache/feature store with TTL
- SQS queue + worker for async refresh
- Nightly precompute Lambda (EventBridge schedule)
- CDK IaC
- WSL + Codex deployment scripts/docs

## Quick start

```bash
bash scripts/bootstrap_wsl.sh
export AWS_PROFILE=default
export AWS_REGION=us-east-1
export STAGE=dev
export APP_NAME=esri-market-delineation
bash scripts/deploy_codex.sh
bash scripts/test_smoke.sh
```

Create ArcGIS secret before testing:
`/esri-market-delineation/<stage>/arcgis` with JSON:
`{"username":"...","password":"..."}`
