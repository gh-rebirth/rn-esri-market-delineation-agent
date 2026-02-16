import os, json, time
import boto3
from common.esri_client import enrich_market, cache_key, DEFAULT_VARS
ddb = boto3.client("dynamodb")

def lambda_handler(event, context):
    errors = []
    for rec in event.get("Records", []):
        msg = json.loads(rec["body"])
        market_id = msg["market_id"]
        radius = msg.get("radius_miles", 1)
        vars_list = msg.get("variables", DEFAULT_VARS)
        include_geometry = bool(msg.get("include_geometry", False))
        try:
            data = enrich_market({"market_id":market_id}, radius, vars_list, include_geometry)
        except Exception as exc:
            errors.append({"market_id": market_id, "error": str(exc)})
            continue
        pk, sk = cache_key(market_id, radius, vars_list)
        ttl = int(time.time()) + 86400
        ddb.put_item(TableName=os.environ["TABLE_NAME"], Item={
            "pk":{"S":pk},"sk":{"S":sk},"payload":{"S":json.dumps(data)},"ttl":{"N":str(ttl)}
        })
    if errors:
        raise RuntimeError(json.dumps({"worker_errors": errors}))
    return {"ok": True}
