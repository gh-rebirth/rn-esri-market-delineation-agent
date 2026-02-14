#!/usr/bin/env python3
import os
import aws_cdk as cdk
from infra.stack import MarketDelineationStack

app = cdk.App()
stage = os.getenv("STAGE", "dev")
app_name = os.getenv("APP_NAME", "esri-market-delineation")
MarketDelineationStack(app, f"{app_name}-{stage}", stage=stage)
app.synth()
