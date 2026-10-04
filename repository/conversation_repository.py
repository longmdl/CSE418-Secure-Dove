import uuid
from datetime import datetime, timezone

from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError

from util.database import conversation_collection

#Prevents duplicate conversations from being created between the same two users.
#The participant IDs are stored in sorted order, so each pair always has the same order.
conversation_collection.create_index( [("participant_ids.0", ASCENDING), ("participant_ids.1", ASCENDING)], unique=True)

#Gets an existing conversation between two users or creates one if it does not exist.
#Parameters:
    #user_a_id: ID of the first user in the conversation.
    #user_b_id: ID of the second user in the conversation.
def open_or_get_conversation_db(user_a_id, user_b_id):
    #Sort the IDs so the same two users always produce the same participant order.
    participant_ids = sorted([user_a_id, user_b_id])
    existing = conversation_collection.find_one({"participant_ids": participant_ids})

    if existing:
        return existing

    #Information stored in MongoDB for a new conversation.
    conversation = {
        "id": str(uuid.uuid4()),
        "participant_ids": participant_ids,
        "created_at": datetime.now(timezone.utc)
    }

    try:
        conversation_collection.insert_one(conversation)
        return conversation
    except DuplicateKeyError:
        #Handles two simultaneous requests that attempt to create the same conversation.
        return conversation_collection.find_one({
            "participant_ids": participant_ids
        })

#Gets a conversation from the database using its conversation ID.
#Parameters:
    #conversation_id: ID of the conversation being searched for.
def get_conversation_db(conversation_id):
    return conversation_collection.find_one({
        "id": conversation_id
    })

#Gets all conversations that contain a specific user.
#Parameters:
    #user_id: ID of the user whose conversations are being requested.
def get_user_conversations_db(user_id):
    return conversation_collection.find({
        "participant_ids": user_id
    })