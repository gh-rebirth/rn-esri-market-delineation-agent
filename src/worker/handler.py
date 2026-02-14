import os, json, time
import boto3
from common.esri_client import fake_enrich, cache_key, DEFAULT_VARS
ddb = boto3.client("dynamodb")

def lambda_handler(event, context):
    for rec in event.get("Records", []):
        msg = json.loads(rec["body"])
        market_id = msg["market_id"]
        radius = msg.get("radius_miles", 1)
        vars_list = msg.get("variables", DEFAULT_VARS)
        include_geometry = bool(msg.get("include_geometry", False))
        data = fake_enrich({"market_id":market_id}, radius, vars_list, include_geometry)
        pk, sk = cache_key(market_id, radius, vars_list)
        ttl = int(time.time()) + 86400
        ddb.put_item(TableName=os.environ["TABLE_NAME"], Item={
            "pk":{"S":pk},"sk":{"S":sk},"payload":{"S":json.dumps(data)},"ttl":{"N":str(ttl)}
        })
    return {"ok": True}
