
# WSL + AWS + Codex CLI Setup (Ubuntu)

This guide prepares your WSL environment so Codex CLI can deploy and test the AWS stack.

## 1) Install base packages
```bash
sudo apt update
sudo apt install -y build-essential unzip jq git curl zip python3 python3-venv python3-pip
```

## 2) Install Node.js 20 LTS + npm
```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
node -v
npm -v
```

## 3) Install AWS CLI v2
```bash
cd /tmp
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o awscliv2.zip
unzip -q awscliv2.zip
sudo ./aws/install --update
aws --version
```

## 4) Configure AWS credentials
Choose one:

### A) AWS SSO (recommended)
```bash
aws configure sso
aws sso login --profile <your-profile>
```

### B) Access key
```bash
aws configure --profile <your-profile>
```

Set defaults for this shell:
```bash
export AWS_PROFILE=<your-profile>
export AWS_REGION=us-east-1
```

## 5) Install CDK CLI
```bash
npm install -g aws-cdk
cdk --version
```

## 6) Python virtual env for repo
From repo root:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt 2>/dev/null || true
pip install -r infra/requirements.txt 2>/dev/null || true
```

## 7) Install Codex CLI
Use your preferred install path (Homebrew/npm/pipx, depending on your Codex distribution).  
Verify:
```bash
codex --help
```

## 8) Sanity checks
```bash
aws sts get-caller-identity
aws configure get region
node -v && npm -v
python3 --version
cdk doctor
```
