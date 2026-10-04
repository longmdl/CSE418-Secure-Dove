
from util.response import Response
from util.auth import verify_jwt
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from service.conversation_service import (
    open_conversation, 
    get_conversations, 
    send_message, 
    get_history,
    edit_message,
    delete_message
    )
import json
import service.websocket_service as ws_service


#Handles all HTTP requests for private conversations and encrypted messages.
#Parameters:
    #request: Contains the HTTP method, path, cookies, query parameters, and request body sent by the user.
    #handler: The connection handler used to send the HTTP response back to the user.
#This controller authenticates the user with their JWT and routes requests to the right conversation service function.
def conversation_controller(request, handler):
    
    res = Response()
    #Parse the request URL so the route path and optional query parameters can be handled separately.
    parsed_url = urlparse(request.path)
    path = parsed_url.path
    query_params = parse_qs(parsed_url.query)

    #HTTP method used to determine which conversation operation was requested
    method = request.method

    #Authenticate the request using the JWT stored in the auth cookie.
    #JWT subject ("sub") is used as the trusted user ID.
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
            if not isinstance(data, dict):
                res.set_status(400, "Bad Request")
                res.json({"error": "Invalid JSON Input"})
                handler.request.sendall(res.to_data())
                return
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

        conversation, status = open_conversation(user_id, other_user_id)

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

        #Conversation ID extracted from the requested URL.
        conversation_id = parts[2]

        try:
            data = json.loads(request.body.decode())
            if not isinstance(data, dict):
                res.set_status(400, "Bad Request")
                res.json({"error": "Invalid JSON Input"})
                handler.request.sendall(res.to_data())
                return
        except (json.JSONDecodeError, UnicodeDecodeError):
            res.set_status(400, "Bad Request")
            res.json({"error": "Invalid JSON Input"})
            handler.request.sendall(res.to_data())
            return

        #Private-message requests may contain encrypted data only.
        #These fields are rejected to prevent readable message content from accidentally being sent to or stored by the server.
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
        
        message, status = send_message(conversation_id, user_id, data)

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

        #Convert server timestamp to JSON-safe format
        message["timestamp"] = message["timestamp"].isoformat()

        #Push the encrypted envelope to the recipient if online
        try:
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
                })
        except Exception as error:
            print("Could not deliver encrypted message over WebSocket:", error)

        res.set_status(201, "Created")
        res.json(message)
        handler.request.sendall(res.to_data())
        return

    elif method == "GET" and path.startswith("/api/conversations/") and path.endswith("/messages"):
        parts = path.strip("/").split("/")

        #Expected:
        #/api/conversations/{conversation_id}/messages
        if len(parts) != 4:
            res.set_status(404, "Not Found")
            res.json({"error": "Not Found"})
            handler.request.sendall(res.to_data())
            return

        conversation_id = parts[2]

        #Maximum/default number of messages requested for one history page.
        limit = 50

        if "limit" in query_params:
            try:
                limit = int(query_params["limit"][0])
            except (ValueError, TypeError):
                res.set_status(400, "Bad Request")
                res.json({"error": "Invalid limit"})
                handler.request.sendall(res.to_data())
                return
        
        #Optional timestamp used to request messages older than this point.
        before = None

        if "before" in query_params:
            try:
                before = datetime.fromisoformat(query_params["before"][0])
            except ValueError:
                res.set_status(400, "Bad Request")
                res.json({"error": "Invalid before timestamp"})
                handler.request.sendall(res.to_data())
                return

        history, status = get_history(conversation_id, user_id, limit, before)

        if status == 404:
            res.set_status(404, "Not Found")
            res.json({"error": "Not Found"})
            handler.request.sendall(res.to_data())
            return

        #Mongo timestamps must be converted before JSON encoding.
        for message in history["messages"]:
            if hasattr(message.get("timestamp"), "isoformat"):
                message["timestamp"] = message["timestamp"].isoformat()

        res.set_status(200, "OK")
        res.json(history)
        handler.request.sendall(res.to_data())
        return

    elif method == "PUT" and path.startswith("/api/conversations/") and "/messages/" in path:
        parts = path.strip("/").split("/")

        #Expected:
        #/api/conversations/{conversation_id}/messages/{sender_id}/{seq}
        if len(parts) != 6:
            res.set_status(404, "Not Found")
            res.json({"error": "Not Found"})
            handler.request.sendall(res.to_data())
            return

        #Sender and sequence number identify the specific encrypted message.
        conversation_id = parts[2]
        sender_id = parts[4]

        try:
            seq = int(parts[5])
        except ValueError:
            res.set_status(400, "Bad Request")
            res.json({"error": "Invalid sequence number"})
            handler.request.sendall(res.to_data())
            return

        try:
            data = json.loads(request.body.decode())
            if not isinstance(data, dict):
                res.set_status(400, "Bad Request")
                res.json({"error": "Invalid JSON Input"})
                handler.request.sendall(res.to_data())
                return
        except (json.JSONDecodeError, UnicodeDecodeError):
            res.set_status(400, "Bad Request")
            res.json({"error": "Invalid JSON Input"})
            handler.request.sendall(res.to_data())
            return

        #Private-message requests may contain encrypted data only.
        #These fields are rejected to prevent readable message content from accidentally being sent to or stored by the server.
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

        message, status = edit_message(
            conversation_id,
            user_id,
            sender_id,
            seq,
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

        res.set_status(200, "OK")
        res.json(message)
        handler.request.sendall(res.to_data())
        return

    elif method == "DELETE" and path.startswith("/api/conversations/") and "/messages/" in path:
        parts = path.strip("/").split("/")

        # Expected:
        # /api/conversations/{conversation_id}/messages/{sender_id}/{seq}
        if len(parts) != 6:
            res.set_status(404, "Not Found")
            res.json({"error": "Not Found"})
            handler.request.sendall(res.to_data())
            return

        #Sender and sequence number identify the specific encrypted message.
        conversation_id = parts[2]
        sender_id = parts[4]

        try:
            seq = int(parts[5])
        except ValueError:
            res.set_status(400, "Bad Request")
            res.json({"error": "Invalid sequence number"})
            handler.request.sendall(res.to_data())
            return

        result, status = delete_message(
            conversation_id,
            user_id,
            sender_id,
            seq
        )

        if status == 404:
            res.set_status(404, "Not Found")
            res.json({"error": "Not Found"})
            handler.request.sendall(res.to_data())
            return

        res.set_status(200, "OK")
        res.json(result)
        handler.request.sendall(res.to_data())
        return