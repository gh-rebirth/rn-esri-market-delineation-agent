import os
from constructs import Construct
from aws_cdk import (
    Stack, Duration, RemovalPolicy,
    aws_lambda as _lambda,
    aws_apigateway as apigw,
    aws_dynamodb as ddb,
    aws_sqs as sqs,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
)
class MarketDelineationStack(Stack):
    def __init__(self, scope: Construct, id: str, stage: str="dev", **kwargs):
        super().__init__(scope, id, **kwargs)

        table = ddb.Table(
            self, "FeatureCache",
            partition_key=ddb.Attribute(name="pk", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="sk", type=ddb.AttributeType.STRING),
            time_to_live_attribute="ttl",
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY
        )

        queue = sqs.Queue(self, "RefreshQueue", visibility_timeout=Duration.seconds(120))

        env = {
            "TABLE_NAME": table.table_name,
            "QUEUE_URL": queue.queue_url,
            "STAGE": stage,
            "APP_NAME": os.getenv("APP_NAME","esri-market-delineation"),
        }

        common_kwargs = dict(
            runtime=_lambda.Runtime.PYTHON_3_11,
            timeout=Duration.seconds(30),
            memory_size=512,
        )

        api_fn = _lambda.Function(
            self, "ApiFn",
            code=_lambda.Code.from_asset("src"),
            handler="api.handler.lambda_handler",
            environment=env,
            **common_kwargs
        )

        worker_fn = _lambda.Function(
            self, "WorkerFn",
            code=_lambda.Code.from_asset("src"),
            handler="worker.handler.lambda_handler",
            environment=env,
            **common_kwargs
        )

        precompute_fn = _lambda.Function(
            self, "PrecomputeFn",
            code=_lambda.Code.from_asset("src"),
            handler="precompute.handler.lambda_handler",
            environment=env,
            timeout=Duration.seconds(120),
            memory_size=1024,
            runtime=_lambda.Runtime.PYTHON_3_11,
        )

        table.grant_read_write_data(api_fn)
        table.grant_read_write_data(worker_fn)
        table.grant_read_write_data(precompute_fn)
        queue.grant_send_messages(api_fn)
        queue.grant_consume_messages(worker_fn)
        queue.grant_send_messages(precompute_fn)

        for fn in [api_fn, worker_fn, precompute_fn]:
            fn.add_to_role_policy(iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"],
                resources=["*"]
            ))

        api = apigw.LambdaRestApi(self, "ServiceApi", handler=api_fn, proxy=False)
        market = api.root.add_resource("market")
        market.add_method("POST")

        events.Rule(
            self, "NightlyPrecompute",
            schedule=events.Schedule.cron(minute="0", hour="5"),
            targets=[targets.LambdaFunction(precompute_fn)]
        )
