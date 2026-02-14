import os, json, time, pathlib
import boto3
from common.esri_client import fake_enrich, cache_key, DEFAULT_VARS
ddb=boto3.client("dynamodb")

def lambda_handler(event, context):
    seed_path = pathlib.Path(__file__).resolve().parents[2] / "config" / "markets_seed.json"
    markets = [{"market_id":"new-york"},{"market_id":"chicago"},{"market_id":"los-angeles"}]
    for m in markets:
        data = fake_enrich(m, 1, DEFAULT_VARS, False)
        pk, sk = cache_key(m["market_id"], 1, DEFAULT_VARS)
        ttl = int(time.time()) + 86400
        ddb.put_item(TableName=os.environ["TABLE_NAME"], Item={
            "pk":{"S":pk},"sk":{"S":sk},"payload":{"S":json.dumps(data)},"ttl":{"N":str(ttl)}
        })
    return {"seeded": len(markets)}
