from pymongo import ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError

from util.database import message_collection


# A sender cannot reuse a sequence number
message_collection.create_index(
    [
        ("sender_id", ASCENDING),
        ("seq", ASCENDING)
    ],
    unique=True
)

# Efficient conversation history
message_collection.create_index(
    [
        ("conversation_id", ASCENDING),
        ("timestamp", DESCENDING)
    ]
)


def insert_message_db(message):
    try:
        message_collection.insert_one(message)
        return True
    except DuplicateKeyError:
        return False


def get_message_db(sender_id, seq):
    return message_collection.find_one({
        "sender_id": sender_id,
        "seq": seq
    })


def get_message_history_db(conversation_id, limit=50, before=None):
    query = {
        "conversation_id": conversation_id
    }

    if before is not None:
        query["timestamp"] = {
            "$lt": before
        }

    messages = list(
        message_collection
        .find(query)
        .sort("timestamp", DESCENDING)
        .limit(limit)
    )

    # Mongo query gets newest first for pagination,
    # but API must return oldest first.
    messages.reverse()

    return messages


def update_message_db(sender_id, seq, updated_data):
    result = message_collection.update_one(
        {
            "sender_id": sender_id,
            "seq": seq
        },
        {
            "$set": updated_data
        }
    )

    return result.matched_count > 0


def delete_message_db(sender_id, seq):
    result = message_collection.delete_one({
        "sender_id": sender_id,
        "seq": seq
    })

    return result.deleted_count > 0