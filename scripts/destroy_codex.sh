#!/usr/bin/env bash
set -euo pipefail
source .venv/bin/activate || true
cdk destroy --force
