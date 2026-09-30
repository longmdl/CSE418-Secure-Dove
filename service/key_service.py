import datetime
import hashlib
import json

from repository.device_key_repository import upsert_device_key, find_device_key

#the fingerprint is a hash of exactly these four fields, serialised with sorted
#keys and no whitespace. public/js/key-api.js builds the same string, so both
#sides always agree on what a key's fingerprint is.
FINGERPRINT_FIELDS = ("crv", "kty", "x", "y")


def canonical_jwk(public_jwk):
    canonical = {field: public_jwk[field] for field in FINGERPRINT_FIELDS}
    return json.dumps(canonical, sort_keys=True, separators=(",", ":"))


def fingerprint(public_jwk):
    return hashlib.sha256(canonical_jwk(public_jwk).encode()).hexdigest()


def validate_public_jwk(public_jwk):
    if not isinstance(public_jwk, dict):
        return "public_jwk must be an object"
    if "d" in public_jwk: #a private key. never accept one, even by accident
        return "public_jwk must not contain a private component"
    if public_jwk.get("kty") != "EC":
        return "public_jwk must be an EC key"
    if public_jwk.get("crv") != "P-256":
        return "public_jwk must use the P-256 curve"
    for field in ("x", "y"):
        value = public_jwk.get(field)
        if not isinstance(value, str) or not 1 <= len(value) <= 128:
            return "public_jwk is missing a valid " + field
    return None


def publish_key(user_id, device_id, public_jwk):
    problem = validate_public_jwk(public_jwk)
    if problem:
        return None, problem

    if not isinstance(device_id, str) or not 1 <= len(device_id) <= 64:
        return None, "device_id must be a short string"

    now = datetime.datetime.utcnow().isoformat() + "Z"
    record = {
        "user_id": user_id,
        "device_id": device_id,
        "public_jwk": {field: public_jwk[field] for field in FINGERPRINT_FIELDS},
        "fingerprint": fingerprint(public_jwk),
        "created_at": now,
        "updated_at": now,
    }
    outcome = upsert_device_key(record)
    return {"fingerprint": record["fingerprint"], "outcome": outcome}, None


def get_key(user_id):
    key = find_device_key(user_id)
    if key is None:
        return None
    return {
        "user_id": key.get("user_id"),
        "device_id": key.get("device_id"),
        "public_jwk": key.get("public_jwk"),
        "fingerprint": key.get("fingerprint"),
    }
