import os, json, time, hashlib
import ast
import urllib.parse
import urllib.request
import boto3

DEFAULT_VARS = ["TOTPOP_CY","DIVINDX_CY","AVGHHSZ_CY","MEDAGE_CY","MEDHINC_CY","BACHDEG_CY"]
TOKEN_URL = "https://www.arcgis.com/sharing/rest/generateToken"
ENRICH_URL = "https://geoenrich.arcgis.com/arcgis/rest/services/World/geoenrichmentserver/GeoEnrichment/enrich"

def get_secret(stage: str):
    sm = boto3.client("secretsmanager")
    name = f"/esri-market-delineation/{stage}/arcgis"
    val = sm.get_secret_value(SecretId=name)["SecretString"]
    parsed = None
    candidates = [val]
    if isinstance(val, str):
        candidates.append(val.strip())
        candidates.append(val.replace('\\"', '"'))

    for cand in candidates:
        if not isinstance(cand, str):
            continue
        try:
            obj = json.loads(cand)
            if isinstance(obj, str):
                try:
                    obj = json.loads(obj)
                except Exception:
                    pass
            if isinstance(obj, dict):
                parsed = obj
                break
        except Exception:
            pass

    if parsed is None:
        for cand in candidates:
            if not isinstance(cand, str):
                continue
            try:
                obj = ast.literal_eval(cand)
                if isinstance(obj, dict):
                    parsed = obj
                    break
            except Exception:
                pass

    if parsed is None:
        try:
            unescaped = bytes(val, "utf-8").decode("unicode_escape")
            obj = json.loads(unescaped)
            if isinstance(obj, dict):
                parsed = obj
        except Exception as exc:
            raise RuntimeError(f"Invalid ArcGIS secret format at {name}: {exc}")

    if not isinstance(parsed, dict):
        raise RuntimeError(f"Invalid ArcGIS secret payload at {name}: expected object")

    username = parsed.get("username") or parsed.get("user") or parsed.get("USERNAME")
    password = parsed.get("password") or parsed.get("pass") or parsed.get("PASSWORD")
    if not username or not password:
        raise RuntimeError(f"Invalid ArcGIS secret payload at {name}: username/password required")
    return {"username": username, "password": password}

def cache_key(market_id, radius_miles, vars_list):
    h = hashlib.sha256(",".join(sorted(vars_list)).encode()).hexdigest()[:10]
    return f"market#{market_id}", f"r#{radius_miles}#v#{h}"

def _post_form(url: str, form: dict, timeout: int = 30):
    body = urllib.parse.urlencode(form).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise RuntimeError(f"Non-JSON response from {url}: {raw[:240]}")

def _to_float(value):
    try:
        return float(value)
    except Exception:
        return 0.0

def _market_text(market: dict):
    if market.get("city") and market.get("state"):
        return f'{market["city"]}, {market["state"]}'
    market_id = str(market.get("market_id") or "").strip().lower()
    if not market_id:
        raise ValueError("market_id (or city/state) is required for ESRI enrich")
    parts = market_id.replace("-", "_").split("_")
    if len(parts) >= 2 and len(parts[-1]) == 2:
        city = " ".join(parts[:-1]).replace("_", " ").title()
        state = parts[-1].upper()
        return f"{city}, {state}"
    return market_id.replace("_", " ").replace("-", " ")

def _study_areas(market: dict):
    if market.get("lat") is not None and market.get("lon") is not None:
        return [{"geometry": {"x": float(market["lon"]), "y": float(market["lat"])}}]
    return [{"address": {"text": _market_text(market)}}]

def _esri_token(stage: str):
    secret = get_secret(stage)
    payload = {
        "username": secret["username"],
        "password": secret["password"],
        "client": "referer",
        "referer": "https://www.arcgis.com",
        "expiration": "60",
        "f": "json",
    }
    data = _post_form(TOKEN_URL, payload, timeout=20)
    token = data.get("token")
    if not token:
        raise RuntimeError(f"ESRI token request failed: {data}")
    return token

def _extract_attrs(node):
    if isinstance(node, dict):
        attrs = node.get("attributes")
        if isinstance(attrs, dict):
            return attrs
        for v in node.values():
            found = _extract_attrs(v)
            if found:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _extract_attrs(item)
            if found:
                return found
    return None

def enrich_market(market, radius_miles=1, vars_list=None, include_geometry=False):
    vars_list = vars_list or DEFAULT_VARS
    stage = os.getenv("STAGE", "dev")
    token = _esri_token(stage)
    req = {
        "f": "json",
        "token": token,
        "studyAreas": json.dumps(_study_areas(market)),
        "analysisVariables": ",".join(vars_list),
        "returnGeometry": "true" if include_geometry else "false",
    }
    data = _post_form(ENRICH_URL, req, timeout=40)
    if data.get("error"):
        raise RuntimeError(f"ESRI enrich failed: {data['error']}")
    attrs = _extract_attrs(data)
    if not attrs:
        raise RuntimeError(f"ESRI enrich payload missing attributes: {data}")

    out = {
        "market_id": market.get("market_id"),
        "as_of_date": time.strftime("%Y-%m-%d"),
        "totpop": _to_float(attrs.get("TOTPOP_CY")),
        "avghhsz": _to_float(attrs.get("AVGHHSZ_CY")),
        "medhinc": _to_float(attrs.get("MEDHINC_CY")),
        "divindx": _to_float(attrs.get("DIVINDX_CY")),
        "medage": _to_float(attrs.get("MEDAGE_CY")),
        "bachdeg": _to_float(attrs.get("BACHDEG_CY")),
        "radius_miles": radius_miles,
        "source": "esri_live",
    }
    if include_geometry:
        out["shape"] = market.get("geometry")
    return out

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
