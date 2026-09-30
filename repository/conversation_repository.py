import uuid
from datetime import datetime, timezone

from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError

from util.database import conversation_collection


# Prevent duplicate conversations between the same two users
conversation_collection.create_index(
    [("participant_ids", ASCENDING)],
    unique=True
)


def open_or_get_conversation_db(user_a_id, user_b_id):
    participant_ids = sorted([user_a_id, user_b_id])

    existing = conversation_collection.find_one({
        "participant_ids": participant_ids
    })

    if existing:
        return existing

    conversation = {
        "id": str(uuid.uuid4()),
        "participant_ids": participant_ids,
        "created_at": datetime.now(timezone.utc)
    }

    try:
        conversation_collection.insert_one(conversation)
        return conversation
    except DuplicateKeyError:
        # Handles two simultaneous "open chat" requests
        return conversation_collection.find_one({
            "participant_ids": participant_ids
        })


def get_conversation_db(conversation_id):
    return conversation_collection.find_one({
        "id": conversation_id
    })


def get_user_conversations_db(user_id):
    return conversation_collection.find({
        "participant_ids": user_id
    })