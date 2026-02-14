import os, json, time
import boto3
from common.esri_client import fake_enrich, cache_key, DEFAULT_VARS

ddb = boto3.client("dynamodb")
sqs = boto3.client("sqs")

def _resp(code, body):
    return {"statusCode": code, "headers":{"Content-Type":"application/json"}, "body": json.dumps(body)}

def lambda_handler(event, context):
    body = json.loads(event.get("body") or "{}")
    market_id = body.get("market_id")
    if not market_id:
        return _resp(400, {"error":"market_id required"})
    radius = body.get("radius_miles", 1)
    vars_list = body.get("variables", DEFAULT_VARS)
    include_geometry = bool(body.get("include_geometry", False))

    pk, sk = cache_key(market_id, radius, vars_list)
    got = ddb.get_item(TableName=os.environ["TABLE_NAME"], Key={"pk":{"S":pk},"sk":{"S":sk}})
    if "Item" in got:
        data = json.loads(got["Item"]["payload"]["S"])
        return _resp(200, {"data": data, "freshness":"cached"})

    # fast fallback: queue refresh and return provisional inline for now
    sqs.send_message(
        QueueUrl=os.environ["QUEUE_URL"],
        MessageBody=json.dumps({"market_id":market_id,"radius_miles":radius,"variables":vars_list,"include_geometry":include_geometry})
    )
    data = fake_enrich({"market_id":market_id}, radius, vars_list, include_geometry)
    ttl = int(time.time()) + 86400
    ddb.put_item(TableName=os.environ["TABLE_NAME"], Item={
        "pk":{"S":pk},"sk":{"S":sk},"payload":{"S":json.dumps(data)},"ttl":{"N":str(ttl)}
    })
    return _resp(200, {"data": data, "freshness":"live"})
