import json

from util.response import Response
from util.auth import verify_jwt
from service.key_service import publish_key, get_key


def key_controller(request, handler):
    res = Response()
    path = request.path
    method = request.method

    payload = verify_jwt(request.cookies.get("auth_token", ""))
    user_id = payload.get("sub") if payload else None

    if not user_id: #the key directory is for logged in users only
        res.set_status(401, "Unauthorized")
        res.json({"error": "Unauthorized"})
        handler.request.sendall(res.to_data())
        return

    if method == "POST" and path == "/api/keys": #publish my own public key
        try:
            body = json.loads(request.body.decode())
        except (ValueError, UnicodeDecodeError):
            res.set_status(400, "Bad Request")
            res.json({"error": "body must be JSON"})
            handler.request.sendall(res.to_data())
            return

        if not isinstance(body, dict):
            res.set_status(400, "Bad Request")
            res.json({"error": "body must be JSON"})
            handler.request.sendall(res.to_data())
            return

        #the key is always filed under the session's user, never a user id from the body
        result, problem = publish_key(user_id, body.get("device_id"), body.get("public_jwk"))

        if problem:
            res.set_status(400, "Bad Request")
            res.json({"error": problem})
            handler.request.sendall(res.to_data())
            return

        res.set_status(200, "OK")
        res.json(result)
        handler.request.sendall(res.to_data())
        return

    if method == "GET" and path.startswith("/api/users/") and path.endswith("/key"): #fetch a peer's key
        peer_id = path[len("/api/users/"):-len("/key")]

        key = get_key(peer_id) if peer_id else None
        if key is None:
            res.set_status(404, "Not Found")
            res.json({"error": "no key for that user"})
            handler.request.sendall(res.to_data())
            return

        res.set_status(200, "OK")
        res.json(key)
        handler.request.sendall(res.to_data())
        return

    res.set_status(404, "Not Found")
    res.json({"error": "not found"})
    handler.request.sendall(res.to_data())
    return
