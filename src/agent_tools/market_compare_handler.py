import json
import os
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

ddb = boto3.resource("dynamodb")
table = ddb.Table(os.environ["DDB_TABLE_NAME"])
W = {"totpop": 0.35, "medhinc": 0.30, "bachdeg": 0.20, "divindx": 0.15}


def _f(x):
    try:
        if isinstance(x, Decimal):
            return float(x)
        return float(x) if x is not None else 0.0
    except Exception:
        return 0.0


def _norm(values):
    values = [_f(v) for v in values]
    mn = min(values)
    mx = max(values)
    return [0.5] * len(values) if mx == mn else [(v - mn) / (mx - mn) for v in values]


def _get_payload(market_id):
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

    market_ids = body.get("market_ids") or []
    top_k = int(body.get("top_k", 3))
    weights = body.get("weights") or W
    if not market_ids:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "market_ids required"}),
        }

    rows = []
    for market_id in market_ids:
        payload = _get_payload(market_id)
        if payload:
            rows.append(
                {
                    "market_id": market_id,
                    "totpop": _f(payload.get("totpop")),
                    "medhinc": _f(payload.get("medhinc")),
                    "bachdeg": _f(payload.get("bachdeg")),
                    "divindx": _f(payload.get("divindx")),
                    "updated_at": payload.get("updated_at"),
                }
            )
    if not rows:
        return {
            "statusCode": 404,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "No markets found"}),
        }

    for metric in ["totpop", "medhinc", "bachdeg", "divindx"]:
        norms = _norm([row[metric] for row in rows])
        for idx, row in enumerate(rows):
            row[f"{metric}_norm"] = norms[idx]

    ranked = []
    for row in rows:
        components = {}
        score = 0.0
        for metric, weight in weights.items():
            contribution = _f(row.get(f"{metric}_norm")) * _f(weight)
            components[metric] = round(contribution, 6)
            score += contribution
        ranked.append(
            {
                "market_id": row["market_id"],
                "score": round(score, 6),
                "components": components,
                "raw": {
                    "totpop": row["totpop"],
                    "medhinc": row["medhinc"],
                    "bachdeg": row["bachdeg"],
                    "divindx": row["divindx"],
                    "updated_at": row["updated_at"],
                },
            }
        )
    ranked.sort(key=lambda x: x["score"], reverse=True)

    out = {
        "ranked": ranked[:top_k],
        "weights": weights,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(out),
    }
