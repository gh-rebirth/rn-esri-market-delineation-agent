
# Codex CLI Deploy Playbook (AWS)

Use this playbook after extracting your repo in WSL.  
Goal: let Codex do most of the work while you run approved commands.

---

## A. One-time bootstrap

From repo root:

```bash
bash scripts/bootstrap_wsl.sh
```

Then set env vars:

```bash
export AWS_PROFILE=<your-profile>
export AWS_REGION=us-east-1
export STAGE=dev
export APP_NAME=esri-market-delineation
```

Bootstrap CDK (once per account/region):

```bash
cd infra
cdk bootstrap aws://$(aws sts get-caller-identity --query Account --output text)/${AWS_REGION}
cd ..
```

---

## B. Create ArcGIS secret before deploy

```bash
aws secretsmanager create-secret   --name "/${APP_NAME}/${STAGE}/arcgis"   --secret-string '{"username":"<arcgis_user>","password":"<arcgis_password>"}'   --region "${AWS_REGION}"   --profile "${AWS_PROFILE}" || aws secretsmanager put-secret-value   --secret-id "/${APP_NAME}/${STAGE}/arcgis"   --secret-string '{"username":"<arcgis_user>","password":"<arcgis_password>"}'   --region "${AWS_REGION}"   --profile "${AWS_PROFILE}"
```

---

## C. Ask Codex to run guided deploy

Suggested Codex prompt:

> Read docs/DEPLOYMENT.md, docs/CODEX_DEPLOY_PLAYBOOK.md, and infra code.  
> Validate prerequisites, run tests/lint if present, synth and deploy CDK to stage `${STAGE}` in `${AWS_REGION}` using profile `${AWS_PROFILE}`.  
> If a command fails, fix root cause and retry once.  
> Print outputs: API URL, table names, queue URL, lambda names, and next test commands.

---

## D. Manual fallback deploy commands

```bash
bash scripts/deploy_codex.sh
```

---

## E. Smoke tests

1) Get API URL from CloudFormation outputs:
```bash
aws cloudformation describe-stacks   --stack-name "${APP_NAME}-${STAGE}"   --query "Stacks[0].Outputs" --output table   --region "${AWS_REGION}" --profile "${AWS_PROFILE}"
```

2) Invoke API:
```bash
API_URL="<paste output URL>"
curl -sS -X POST "${API_URL}/market"   -H "Content-Type: application/json"   -d '{"market_id":"atlanta_ga","lat":33.7490,"lon":-84.3880,"radius_miles":1,"include_geometry":false}' | jq
```

3) Re-run same request to verify cache hit + lower latency.

---

## F. Common failure fixes

- **AccessDenied on deploy**: wrong AWS profile/role; confirm `aws sts get-caller-identity`.
- **CDK bootstrap missing**: run `cdk bootstrap`.
- **Lambda import errors**: ensure dependencies bundled in function package/layer.
- **Secret not found**: check exact path `/${APP_NAME}/${STAGE}/arcgis`.
- **429/timeout from ESRI**: reduce concurrency, increase retry backoff, rely on cached responses.

---

## G. Destroy stack

```bash
bash scripts/destroy_codex.sh
```
