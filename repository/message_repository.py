from pymongo import ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError

from util.database import message_collection


#A sender cannot reuse a sequence number
message_collection.create_index(
    [
        ("sender_id", ASCENDING),
        ("seq", ASCENDING)
    ],
    unique=True
)

#Allows conversation history to be efficiently sorted and paginated by timestamp.
message_collection.create_index(
    [
        ("conversation_id", ASCENDING),
        ("timestamp", DESCENDING)
    ]
)

#Stores an encrypted message in the database
#Parameters:
    #message: Encrypted message data to store in the messages collection
def insert_message_db(message):
    try:
        result = message_collection.insert_one(message)
        return result.inserted_id
    except DuplicateKeyError:
         #A duplicate sender ID and sequence number cannot be stored.
        return None

#Gets a specific message using its sender ID and sequence number.
#Parameters:
    #sender_id: ID of the user who sent the message
    #seq: Sequence number identifying the sender's message
def get_message_db(sender_id, seq):
    return message_collection.find_one({
        "sender_id": sender_id,
        "seq": seq
    })

#Gets a page of encrypted message history for a conversation.
#Parameters:
    #conversation_id: ID of the conversation whose messages are being requested
    #limit: Maximum number of messages to return. Defaults to 50.
    #before: Optional timestamp used to request messages older than this point.
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

    #MongoDB gets the newest messages first for pagination, but the API must return them oldest first
    messages.reverse()

    return messages

#Updates the encrypted contents of a specific message
#Parameters:
    #sender_id: ID of the user who sent the message
    #seq: Sequence number identifying the sender's message.
    #updated_data: Encrypted message fields that will replace the existing values
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

#Deletes a specific message from the database
#Parameters:
    #sender_id: ID of the user who sent the message
    #seq: Sequence number identifying the sender's message
def delete_message_db(sender_id, seq):
    result = message_collection.delete_one({
        "sender_id": sender_id,
        "seq": seq
    })

    return result.deleted_count > 0