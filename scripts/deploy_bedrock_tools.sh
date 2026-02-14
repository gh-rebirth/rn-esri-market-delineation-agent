#!/usr/bin/env bash
set -euo pipefail
: "${AWS_REGION:=us-east-1}"
: "${STAGE:=dev}"
: "${APP_NAME:=esri-market-delineation}"
STACK_NAME="${APP_NAME}-${STAGE}-bedrock-tools"
BASE_STACK_NAME="${APP_NAME}-${STAGE}"

if [ -z "${DDB_TABLE_NAME:-}" ]; then
  DDB_TABLE_NAME=$(aws cloudformation describe-stack-resources \
    --region "$AWS_REGION" \
    --stack-name "$BASE_STACK_NAME" \
    --query "StackResources[?ResourceType=='AWS::DynamoDB::Table' && contains(LogicalResourceId, 'FeatureCache')].PhysicalResourceId | [0]" \
    --output text)
fi

if [ -z "${DDB_TABLE_NAME:-}" ] || [ "$DDB_TABLE_NAME" = "None" ]; then
  echo "Unable to resolve DDB_TABLE_NAME from stack ${BASE_STACK_NAME}. Set DDB_TABLE_NAME explicitly."
  exit 1
fi

cat > infra/bedrock_tools_stack.yaml <<'YAML'
AWSTemplateFormatVersion: '2010-09-09'
Description: Bedrock Market Tools API (Lambda + API Gateway)
Parameters:
  AppName: {Type: String, Default: esri-market-delineation}
  Stage: {Type: String, Default: dev}
  DdbTableName: {Type: String}
Resources:
  AgentToolsRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: !Sub '${AppName}-${Stage}-agent-tools-role'
      AssumeRolePolicyDocument: {Version: '2012-10-17', Statement: [{Effect: Allow, Principal: {Service: [lambda.amazonaws.com]}, Action: ['sts:AssumeRole']}]}
      ManagedPolicyArns: [arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole]
      Policies:
        - PolicyName: ddb-read
          PolicyDocument:
            Version: '2012-10-17'
            Statement: [{Effect: Allow, Action: [dynamodb:GetItem,dynamodb:BatchGetItem,dynamodb:Query,dynamodb:Scan], Resource: !Sub 'arn:aws:dynamodb:${AWS::Region}:${AWS::AccountId}:table/${DdbTableName}'}]
  MarketProfileFn:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: !Sub '${AppName}-${Stage}-market-profile'
      Handler: market_profile_handler.handler
      Role: !GetAtt AgentToolsRole.Arn
      Runtime: python3.11
      Timeout: 15
      Environment: {Variables: {DDB_TABLE_NAME: !Ref DdbTableName}}
      Code: {ZipFile: "def handler(event, context):\n  return {'statusCode':500,'body':'placeholder'}"}
  MarketCompareFn:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: !Sub '${AppName}-${Stage}-market-compare'
      Handler: market_compare_handler.handler
      Role: !GetAtt AgentToolsRole.Arn
      Runtime: python3.11
      Timeout: 20
      Environment: {Variables: {DDB_TABLE_NAME: !Ref DdbTableName}}
      Code: {ZipFile: "def handler(event, context):\n  return {'statusCode':500,'body':'placeholder'}"}
  Api:
    Type: AWS::ApiGatewayV2::Api
    Properties: {Name: !Sub '${AppName}-${Stage}-agent-tools-api', ProtocolType: HTTP}
  StageResource:
    Type: AWS::ApiGatewayV2::Stage
    Properties: {ApiId: !Ref Api, StageName: !Ref Stage, AutoDeploy: true}
  ProfileIntegration:
    Type: AWS::ApiGatewayV2::Integration
    Properties: {ApiId: !Ref Api, IntegrationType: AWS_PROXY, IntegrationUri: !GetAtt MarketProfileFn.Arn, PayloadFormatVersion: '2.0'}
  CompareIntegration:
    Type: AWS::ApiGatewayV2::Integration
    Properties: {ApiId: !Ref Api, IntegrationType: AWS_PROXY, IntegrationUri: !GetAtt MarketCompareFn.Arn, PayloadFormatVersion: '2.0'}
  ProfileRoute:
    Type: AWS::ApiGatewayV2::Route
    Properties: {ApiId: !Ref Api, RouteKey: 'POST /tools/market-profile', Target: !Sub 'integrations/${ProfileIntegration}'}
  CompareRoute:
    Type: AWS::ApiGatewayV2::Route
    Properties: {ApiId: !Ref Api, RouteKey: 'POST /tools/market-compare', Target: !Sub 'integrations/${CompareIntegration}'}
  PermProfileInvoke:
    Type: AWS::Lambda::Permission
    Properties: {Action: lambda:InvokeFunction, FunctionName: !Ref MarketProfileFn, Principal: apigateway.amazonaws.com, SourceArn: !Sub 'arn:aws:execute-api:${AWS::Region}:${AWS::AccountId}:${Api}/*/*/tools/market-profile'}
  PermCompareInvoke:
    Type: AWS::Lambda::Permission
    Properties: {Action: lambda:InvokeFunction, FunctionName: !Ref MarketCompareFn, Principal: apigateway.amazonaws.com, SourceArn: !Sub 'arn:aws:execute-api:${AWS::Region}:${AWS::AccountId}:${Api}/*/*/tools/market-compare'}
Outputs:
  ApiBaseUrl: {Value: !Sub 'https://${Api}.execute-api.${AWS::Region}.amazonaws.com/${Stage}'}
  MarketProfileFunction: {Value: !Ref MarketProfileFn}
  MarketCompareFunction: {Value: !Ref MarketCompareFn}
YAML

rm -rf ./.dist && mkdir -p ./.dist/profile ./.dist/compare
cp src/agent_tools/market_profile_handler.py ./.dist/profile/
cp src/agent_tools/market_compare_handler.py ./.dist/compare/
( cd ./.dist/profile && zip -q profile.zip market_profile_handler.py )
( cd ./.dist/compare && zip -q compare.zip market_compare_handler.py )

aws cloudformation deploy --region "$AWS_REGION" --stack-name "$STACK_NAME" --template-file infra/bedrock_tools_stack.yaml --capabilities CAPABILITY_NAMED_IAM --parameter-overrides AppName="$APP_NAME" Stage="$STAGE" DdbTableName="$DDB_TABLE_NAME"

PROFILE_FN=$(aws cloudformation describe-stacks --region "$AWS_REGION" --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='MarketProfileFunction'].OutputValue" --output text)
COMPARE_FN=$(aws cloudformation describe-stacks --region "$AWS_REGION" --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='MarketCompareFunction'].OutputValue" --output text)
API_BASE=$(aws cloudformation describe-stacks --region "$AWS_REGION" --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='ApiBaseUrl'].OutputValue" --output text)

aws lambda update-function-code --region "$AWS_REGION" --function-name "$PROFILE_FN" --zip-file fileb://./.dist/profile/profile.zip >/dev/null
aws lambda update-function-code --region "$AWS_REGION" --function-name "$COMPARE_FN" --zip-file fileb://./.dist/compare/compare.zip >/dev/null

cp bedrock/openapi-market-tools.yaml ./.dist/openapi-market-tools.resolved.yaml
sed -i "s#https://REPLACE_WITH_API_ID.execute-api.REPLACE_REGION.amazonaws.com/REPLACE_STAGE#${API_BASE}#g" ./.dist/openapi-market-tools.resolved.yaml
echo "API_BASE_URL=$API_BASE"
echo "Resolved OpenAPI: ./.dist/openapi-market-tools.resolved.yaml"
