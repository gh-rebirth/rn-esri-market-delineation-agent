#!/usr/bin/env bash
set -euo pipefail
source .venv/bin/activate
: "${AWS_REGION:=us-east-1}"
: "${STAGE:=dev}"
: "${APP_NAME:=esri-market-delineation}"
cdk bootstrap aws://$(aws sts get-caller-identity --query Account --output text)/$AWS_REGION
cdk deploy --require-approval never
