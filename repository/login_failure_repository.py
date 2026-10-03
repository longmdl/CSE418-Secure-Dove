import datetime

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from util.database import login_failures_collection

#SD-12 per-account lockout. nginx limits by IP but can't see usernames, so this
#catches one account being guessed at from many IPs. one doc per typed username,
#_id is the username. every write is a single atomic mongo update, so no lock is
#needed even though the server runs a thread per connection.
LOCKOUT_AFTER = 5 #failed logins in a row before the account locks
LOCKOUT_SECONDS = 300 #5 minutes


def is_locked_out_db(username):
    entry = login_failures_collection.find_one({"_id": username})
    if entry is None or entry.get("locked_until") is None:
        return False
    return entry["locked_until"] > datetime.datetime.utcnow()


def record_failed_login_db(username):
    try:
        entry = login_failures_collection.find_one_and_update(
            {"_id": username},
            {"$inc": {"failures": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER)
    except DuplicateKeyError: #two threads created the doc at once, the doc exists now so just retry
        return record_failed_login_db(username)

    if entry["failures"] == LOCKOUT_AFTER: #== so two racing failures can't both lock and double count
        locked_until = datetime.datetime.utcnow() + datetime.timedelta(seconds=LOCKOUT_SECONDS)
        #start the count over so the account gets a fresh 5 tries once the lockout ends.
        #lockouts is never reset, it's the counter SD-13 reports
        login_failures_collection.update_one(
            {"_id": username},
            {"$set": {"failures": 0, "locked_until": locked_until}, "$inc": {"lockouts": 1}})


def reset_failed_logins_db(username):
    login_failures_collection.update_one({"_id": username}, {"$set": {"failures": 0}})


def count_lockouts_db():
    total = 0
    for entry in login_failures_collection.find({}, {"lockouts": 1}):
        total += entry.get("lockouts", 0)
    return total
