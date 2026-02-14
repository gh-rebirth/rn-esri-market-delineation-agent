import os, json, time, hashlib
import boto3

DEFAULT_VARS = ["TOTPOP_CY","DIVINDX_CY","AVGHHSZ_CY","MEDAGE_CY","MEDHINC_CY","BACHDEG_CY"]

def get_secret(stage: str):
    sm = boto3.client("secretsmanager")
    name = f"/esri-market-delineation/{stage}/arcgis"
    val = sm.get_secret_value(SecretId=name)["SecretString"]
    return json.loads(val)

def cache_key(market_id, radius_miles, vars_list):
    h = hashlib.sha256(",".join(sorted(vars_list)).encode()).hexdigest()[:10]
    return f"market#{market_id}", f"r#{radius_miles}#v#{h}"

def fake_enrich(market, radius_miles=1, vars_list=None, include_geometry=False):
    vars_list = vars_list or DEFAULT_VARS
    # Placeholder for real ArcGIS enrich call.
    # Return compact schema for agent use.
    out = {
        "market_id": market.get("market_id"),
        "as_of_date": time.strftime("%Y-%m-%d"),
        "totpop": 100000,
        "avghhsz": 2.6,
        "medhinc": 85000,
        "divindx": 63.2,
        "medage": 36.1,
        "bachdeg": 41.4,
        "radius_miles": radius_miles,
        "source": "esri",
    }
    if include_geometry:
        out["shape"] = market.get("geometry")
    return out
