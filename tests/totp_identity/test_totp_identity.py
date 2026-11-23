import sys, os, types

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO_ROOT)

class FakeCollection:
    def __init__(self): self.docs = []
    def _match(self, doc, query): return all(doc.get(k) == v for k, v in query.items())
    def find_one(self, query):
        for d in self.docs:
            if self._match(d, query): return d
        return None
    def update_one(self, query, update):
        class R: modified_count = 0
        r = R()
        for d in self.docs:
            if self._match(d, query):
                for k, v in update.get("$set", {}).items(): d[k] = v
                for k in update.get("$unset", {}): d.pop(k, None)
                r.modified_count = 1
                break
        return r
    def insert_one(self, doc): self.docs.append(dict(doc))
    def create_index(self, *a, **k): pass

fake = FakeCollection()
fake_db = types.ModuleType("util.database")
fake_db.user_collection = fake
sys.modules["util.database"] = fake_db

from repository.auth_repository import enable_otp_db, get_user_by_id_db

passed = failed = 0
def check(name, cond):
    global passed, failed
    print(("PASS " if cond else "FAIL ") + name)
    passed += 1 if cond else 0
    failed += 0 if cond else 1

fake.insert_one({"id": "A-id", "username": "Alice_new", "totp_secret": None})
fake.insert_one({"id": "B-id", "username": "Alice",     "totp_secret": "B_ORIGINAL_SECRET"})

enable_otp_db("A-id")

a = get_user_by_id_db("A-id")
b = get_user_by_id_db("B-id")

check("A's own account received the pending secret", a.get("pending_totp_secret") is not None)
check("B's active 2FA secret is unchanged", b.get("totp_secret") == "B_ORIGINAL_SECRET")
check("B received no pending secret from A's token", b.get("pending_totp_secret") is None)
check("A's active secret not activated without confirm", a.get("totp_secret") is None)

print()
print(str(passed) + " passed, " + str(failed) + " failed")
sys.exit(1 if failed else 0)
