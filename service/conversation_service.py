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


def assert_member(conversation_id, user_id):
    conversation = get_conversation_db(conversation_id)

    if conversation is None:
        return None

    if user_id not in conversation["participant_ids"]:
        return None

    return conversation


def open_conversation(user_id, other_user_id):
    # Cannot open a conversation with yourself
    if user_id == other_user_id:
        return None, 400

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


def get_conversations(user_id):
    conversations = get_user_conversations_db(user_id)

    result = []

    for conversation in conversations:
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


def send_message(conversation_id, user_id, data):
    conversation = assert_member(
        conversation_id,
        user_id
    )

    # Missing conversation AND unauthorized user both become 404
    if conversation is None:
        return None, 404

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

    # Ciphertext <= 16 KB
    if len(ciphertext.encode("utf-8")) > 16 * 1024:
        return None, 400

    # IV must be valid base64 representing exactly 12 bytes
    try:
        decoded_iv = base64.b64decode(iv, validate=True)
    except (binascii.Error, ValueError):
        return None, 400

    if len(decoded_iv) != 12:
        return None, 400

    # Find the OTHER participant ourselves.
    # Never trust recipient_id from the request.
    recipient_id = next(
        participant_id
        for participant_id in conversation["participant_ids"]
        if participant_id != user_id
    )

    message = {
        "conversation_id": conversation_id,

        # Comes from JWT
        "sender_id": user_id,

        # Comes from conversation
        "recipient_id": recipient_id,

        "seq": seq,
        "ciphertext": ciphertext,
        "iv": iv,
        "timestamp": datetime.now(timezone.utc)
    }

    inserted_id = insert_message_db(message)

    if inserted_id is None:
        # Duplicate (sender_id, seq)
        return None, 409

    message.pop("_id", None)
    message["id"] = str(inserted_id)

    return message, 201


def get_history(conversation_id, user_id, limit=50, before=None):
    conversation = assert_member(
        conversation_id,
        user_id
    )

    if conversation is None:
        return None, 404

    # Prevent ridiculous page sizes
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