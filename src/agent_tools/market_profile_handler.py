import json
import os
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

ddb = boto3.resource("dynamodb")
table = ddb.Table(os.environ["DDB_TABLE_NAME"])


def _f(x):
    try:
        if isinstance(x, Decimal):
            return float(x)
        return float(x) if x is not None else 0.0
    except Exception:
        return 0.0


def _slug(city, state):
    return f"{city.strip().lower().replace(' ', '_')}_{state.strip().lower()}"


def _load_market_payload(market_id):
    resp = table.query(
        KeyConditionExpression=Key("pk").eq(f"market#{market_id}"),
        Limit=1,
    )
    items = resp.get("Items") or []
    if not items:
        return None

    payload = items[0].get("payload")
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return None
    if isinstance(payload, dict):
        return payload
    return None


def handler(event, context):
    body = event.get("body", event) if isinstance(event, dict) else {}
    if isinstance(body, str):
        body = json.loads(body or "{}")
    if not isinstance(body, dict):
        body = {}

    market_id = body.get("market_id") or (
        _slug(body.get("city"), body.get("state"))
        if body.get("city") and body.get("state")
        else None
    )
    if not market_id:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "market_id or city/state required"}),
        }

    payload = _load_market_payload(market_id)
    if not payload:
        return {
            "statusCode": 404,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": f"market not found: {market_id}"}),
        }

    out = {
        "market_id": market_id,
        "features": {
            "totpop": _f(payload.get("totpop")),
            "medhinc": _f(payload.get("medhinc")),
            "divindx": _f(payload.get("divindx")),
            "bachdeg": _f(payload.get("bachdeg")),
            "medage": _f(payload.get("medage")),
            "avghhsz": _f(payload.get("avghhsz")),
        },
        "freshness": {
            "updated_at": payload.get("updated_at"),
            "as_of_date": payload.get("as_of_date"),
        },
    }
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(out),
    }
