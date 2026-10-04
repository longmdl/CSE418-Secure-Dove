
from util.response import Response
from util.auth import verify_jwt
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from service.conversation_service import (
    open_conversation, 
    get_conversations, 
    send_message, 
    get_history
    )
import json
import service.websocket_service as ws_service


def conversation_controller(request, handler):
    res = Response()
    parsed_url = urlparse(request.path)
    path = parsed_url.path
    query_params = parse_qs(parsed_url.query)

    method = request.method

    auth_token = request.cookies.get("auth_token", "")
    payload = verify_jwt(auth_token)
    user_id = payload.get("sub") if payload else None

    if not user_id:
        res.set_status(401, "Unauthorized")
        res.json({"error": "Unauthorized"})
        handler.request.sendall(res.to_data())
        return

    if method == "POST" and path == "/api/conversations":
        try:
            data = json.loads(request.body.decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            res.set_status(400, "Bad Request")
            res.json({"error": "Invalid JSON Input"})
            handler.request.sendall(res.to_data())
            return

        other_user_id = data.get("user_id")

        if not isinstance(other_user_id, str) or not other_user_id:
            res.set_status(400, "Bad Request")
            res.json({"error": "Missing field: user_id"})
            handler.request.sendall(res.to_data())
            return

        conversation, status = open_conversation(
            user_id,
            other_user_id
        )

        if status == 400:
            res.set_status(400, "Bad Request")
            res.json({"error": "Cannot open a conversation with yourself"})
            handler.request.sendall(res.to_data())
            return

        if status == 404:
            res.set_status(404, "Not Found")
            res.json({"error": "Not Found"})
            handler.request.sendall(res.to_data())
            return

        res.set_status(200, "OK")
        res.json(conversation)
        handler.request.sendall(res.to_data())
        return

    elif method == "GET" and path == "/api/conversations":
        conversations = get_conversations(user_id)

        res.set_status(200, "OK")
        res.json(conversations)
        handler.request.sendall(res.to_data())
        return

    elif method == "POST" and path.startswith("/api/conversations/") and path.endswith("/messages"):
        parts = path.strip("/").split("/")

        # Expected:
        # /api/conversations/{conversation_id}/messages
        if len(parts) != 4:
            res.set_status(404, "Not Found")
            res.json({"error": "Not Found"})
            handler.request.sendall(res.to_data())
            return

        conversation_id = parts[2]

        try:
            data = json.loads(request.body.decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            res.set_status(400, "Bad Request")
            res.json({"error": "Invalid JSON Input"})
            handler.request.sendall(res.to_data())
            return

        forbidden_fields = {
            "text",
            "content",
            "body",
            "message"
        }

        if any(field in data for field in forbidden_fields):
            res.set_status(400, "Bad Request")
            res.json({"error": "Readable message fields are not allowed"})
            handler.request.sendall(res.to_data())
            return
        
        message, status = send_message(
            conversation_id,
            user_id,
            data
        )

        if status == 400:
            res.set_status(400, "Bad Request")
            res.json({"error": "Invalid encrypted message"})
            handler.request.sendall(res.to_data())
            return

        if status == 404:
            res.set_status(404, "Not Found")
            res.json({"error": "Not Found"})
            handler.request.sendall(res.to_data())
            return

        if status == 409:
            res.set_status(409, "Conflict")
            res.json({"error": "Duplicate message"})
            handler.request.sendall(res.to_data())
            return

        # Convert server timestamp to JSON-safe format
        message["timestamp"] = message["timestamp"].isoformat()

        # Push the encrypted envelope to the recipient if online
        ws_service.send_to_user(
            message["recipient_id"],
            {
                "messageType": "encrypted_message",
                "id": message["id"],
                "conversation_id": message["conversation_id"],
                "sender_id": message["sender_id"],
                "recipient_id": message["recipient_id"],
                "seq": message["seq"],
                "ciphertext": message["ciphertext"],
                "iv": message["iv"],
                "timestamp": message["timestamp"]
            }
        )

        res.set_status(201, "Created")
        res.json(message)
        handler.request.sendall(res.to_data())
        return

    elif method == "GET" and path.startswith("/api/conversations/") and path.endswith("/messages"):
        parts = path.strip("/").split("/")

        # Expected:
        # /api/conversations/{conversation_id}/messages
        if len(parts) != 4:
            res.set_status(404, "Not Found")
            res.json({"error": "Not Found"})
            handler.request.sendall(res.to_data())
            return

        conversation_id = parts[2]

        # Default page size
        limit = 50

        if "limit" in query_params:
            try:
                limit = int(query_params["limit"][0])
            except (ValueError, TypeError):
                res.set_status(400, "Bad Request")
                res.json({"error": "Invalid limit"})
                handler.request.sendall(res.to_data())
                return

        before = None

        if "before" in query_params:
            try:
                before = datetime.fromisoformat(query_params["before"][0])
            except ValueError:
                res.set_status(400, "Bad Request")
                res.json({"error": "Invalid before timestamp"})
                handler.request.sendall(res.to_data())
                return

        history, status = get_history(
            conversation_id,
            user_id,
            limit,
            before
        )

        if status == 404:
            res.set_status(404, "Not Found")
            res.json({"error": "Not Found"})
            handler.request.sendall(res.to_data())
            return

        # Mongo timestamps must be converted before JSON encoding.
        for message in history["messages"]:
            if hasattr(message.get("timestamp"), "isoformat"):
                message["timestamp"] = message["timestamp"].isoformat()

        res.set_status(200, "OK")
        res.json(history)
        handler.request.sendall(res.to_data())
        return