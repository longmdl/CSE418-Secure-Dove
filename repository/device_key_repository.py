from util.database import public_keys_collection

#one active key per user. the unique index is what makes that true even if two
#tabs publish at the same moment.
public_keys_collection.create_index("user_id", unique=True)


def upsert_device_key(record):
    user_id = record["user_id"]
    existing = public_keys_collection.find_one({"user_id": user_id})

    if existing is None:
        public_keys_collection.insert_one(dict(record))
        return "created"

    if existing.get("fingerprint") == record["fingerprint"]: #same key published again, nothing to do
        return "unchanged"

    public_keys_collection.update_one(
        {"user_id": user_id},
        {"$set": {
            "device_id": record["device_id"],
            "public_jwk": record["public_jwk"],
            "fingerprint": record["fingerprint"],
            "updated_at": record["updated_at"],
        }})
    return "rotated"


def find_device_key(user_id):
    key = public_keys_collection.find_one({"user_id": user_id})
    if key is None:
        return None
    key.pop("_id", None)
    return key
