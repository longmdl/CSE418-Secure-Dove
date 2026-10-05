import base64
import binascii
from datetime import datetime, timezone

from util.database import user_collection

from repository.conversation_repository import (
    open_or_get_conversation_db,
    get_conversation_db,
    get_user_conversations_db
)

from repository.message_repository import (
    insert_message_db,
    get_message_history_db,
    get_message_db,
    update_message_db,
    delete_message_db
)

#Checks whether a user is a participant in a specific conversation.
#Parameters:
    #conversation_id: ID of the conversation being accessed.
    #user_id: ID of the authenticated user trying to access the conversation.
def assert_member(conversation_id, user_id):
    conversation = get_conversation_db(conversation_id)

    if conversation is None:
        return None

    if user_id not in conversation["participant_ids"]:
        return None

    return conversation

#Opens an existing conversation or creates a new conversation between two users.
#Parameters:
    #user_id: ID of the authenticated user opening the conversation.
    #other_user_id: ID of the other user in the conversation.
def open_conversation(user_id, other_user_id):
    #A user cannot open a conversation with themselves.
    if user_id == other_user_id:
        return None, 400

    #Check that the other user actually exists before opening the conversation.
    other_user = user_collection.find_one({
        "id": other_user_id
    })

    if other_user is None:
        return None, 404

    conversation = open_or_get_conversation_db(user_id, other_user_id)
    conversation.pop("_id", None)

    if hasattr(conversation.get("created_at"), "isoformat"):
        conversation["created_at"] = conversation["created_at"].isoformat()

    return conversation, 200

#Gets all conversations belonging to a user and includes information about the other participant.
#Parameters:
    #user_id: ID of the authenticated user whose conversations are being requested.
def get_conversations(user_id):
    conversations = get_user_conversations_db(user_id)

    #Stores the conversation information that will be returned to the user.
    result = []

    for conversation in conversations:
        #Find the participant who is not the authenticated user.
        other_user_id = next( 
            participant_id 
            for participant_id in conversation["participant_ids"]
            if participant_id != user_id
        )

        other_user = user_collection.find_one({
            "id": other_user_id
        })

        result.append({
            "id": conversation["id"],
            "other_participant": {
                "id": other_user_id,
                "username": other_user.get("username") if other_user else None
            }
        })

    return {"conversations": result}

#Validates and stores an encrypted private message.
#Parameters:
    #conversation_id: ID of the conversation receiving the message.
    #user_id: ID of the authenticated user sending the message.
    #data: Encrypted message data containing ciphertext, IV, and sequence number.
def send_message(conversation_id, user_id, data):
    conversation = assert_member(
        conversation_id,
        user_id
    )

    #Missing conversations and unauthorized users both return 404.
    if conversation is None:
        return None, 404

    #Encrypted message contents and sequence number supplied by the user's browser.
    ciphertext = data.get("ciphertext")
    iv = data.get("iv")
    seq = data.get("seq")

    if ciphertext is None or iv is None or seq is None:
        return None, 400

    if not isinstance(ciphertext, str):
        return None, 400

    if not isinstance(iv, str):
        return None, 400

    if not isinstance(seq, int):
        return None, 400

    #Encrypted ciphertext cannot be larger than 16 KB.
    if len(ciphertext.encode("utf-8")) > 16 * 1024:
        return None, 400

    #AES-GCM requires the IV used by this application to decode to exactly 12 bytes.
    try:
        decoded_iv = base64.b64decode(iv, validate=True)
    except (binascii.Error, ValueError):
        return None, 400

    if len(decoded_iv) != 12:
        return None, 400

    #Get the recipient from the conversation instead of trusting recipient_id from the request.
    recipient_id = next(
        participant_id
        for participant_id in conversation["participant_ids"]
        if participant_id != user_id
    )

    message = {
        "conversation_id": conversation_id,

        #Comes from JWT
        "sender_id": user_id,

        #Comes from conversation participants
        "recipient_id": recipient_id,

        "seq": seq,
        "ciphertext": ciphertext,
        "iv": iv,
        "timestamp": datetime.now(timezone.utc)
    }

    inserted_id = insert_message_db(message)

    #A sender cannot reuse the same sequence number.
    if inserted_id is None:
        # Duplicate (sender_id, seq)
        return None, 409

    message.pop("_id", None)
    message["id"] = str(inserted_id)

    return message, 201

#Gets a page of encrypted message history for a conversation.
#Parameters:
    #conversation_id: ID of the conversation whose messages are being requested.
    #user_id: ID of the authenticated user requesting the history.
    #limit: Maximum number of messages to return. Defaults to 50.
    #before: Optional timestamp used to request messages older than this point.
def get_history(conversation_id, user_id, limit=50, before=None):
    conversation = assert_member(
        conversation_id,
        user_id
    )

    if conversation is None:
        return None, 404

    #Keep the requested history page size between 1 and 50 messages.
    if limit < 1:
        limit = 1
    elif limit > 50:
        limit = 50

    messages = get_message_history_db(
        conversation_id,
        limit,
        before
    )

    for message in messages:
        message.pop("_id", None)

    return {"messages": messages}, 200

#Updates the encrypted ciphertext and IV of a message owned by the authenticated user.
#Parameters:
    #conversation_id: ID of the conversation containing the message.
    #user_id: ID of the authenticated user requesting the edit.
    #sender_id: ID of the user who originally sent the message.
    #seq: Sequence number identifying the sender's message.
    #data: New encrypted message data containing ciphertext and IV.
def edit_message(conversation_id, user_id, sender_id, seq, data):
    #Only conversation participants may access messages in this conversation.
    conversation = assert_member(conversation_id, user_id)

    if conversation is None:
        return None, 404

    #A user may only edit their own message.
    if sender_id != user_id:
        return None, 404

    message = get_message_db(sender_id, seq)

    #Hide whether another user's message exists.
    if message is None:
        return None, 404

    #Make sure the message actually belongs to this conversation.
    if message.get("conversation_id") != conversation_id:
        return None, 404

    ciphertext = data.get("ciphertext")
    iv = data.get("iv")

    if ciphertext is None or iv is None:
        return None, 400

    if not isinstance(ciphertext, str):
        return None, 400

    if not isinstance(iv, str):
        return None, 400

    #Encrypted ciphertext cannot be larger than 16 KB.
    if len(ciphertext.encode("utf-8")) > 16 * 1024:
        return None, 400

    #IV must be valid base64 representing exactly 12 bytes.
    try:
        decoded_iv = base64.b64decode(iv, validate=True)
    except (binascii.Error, ValueError):
        return None, 400

    if len(decoded_iv) != 12:
        return None, 400

    #Only the encrypted contents are replaced in the database.
    updated = update_message_db(
        sender_id,
        seq,
        {
            "ciphertext": ciphertext,
            "iv": iv
        }
    )

    if not updated:
        return None, 404

    return {
        "sender_id": sender_id,
        "seq": seq,
        "ciphertext": ciphertext,
        "iv": iv
    }, 200

#Deletes a message owned by the authenticated user.
#Parameters:
    #conversation_id: ID of the conversation containing the message.
    #user_id: ID of the authenticated user requesting the deletion.
    #sender_id: ID of the user who originally sent the message.
    #seq: Sequence number identifying the sender's message.
def delete_message(conversation_id, user_id, sender_id, seq):
    #Only conversation participants may access messages in this conversation.
    conversation = assert_member(conversation_id, user_id)

    if conversation is None:
        return None, 404

    #A user may only delete their own message.
    if sender_id != user_id:
        return None, 404

    message = get_message_db(sender_id, seq)

    if message is None:
        return None, 404

    #Prevent accessing a message through the wrong conversation ID.
    if message.get("conversation_id") != conversation_id:
        return None, 404
        
    #Delete the message only after all authorization checks have passed.
    deleted = delete_message_db(sender_id, seq)

    if not deleted:
        return None, 404

    return {"deleted": True}, 200