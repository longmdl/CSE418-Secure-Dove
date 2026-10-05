from util.response import Response
from service.chat_service import remove_legacy_chat_data
from util.auth import verify_jwt


# Run the legacy-data cleanup when this controller is imported at server startup.
# MongoDB drop() is idempotent, so restarting the application is safe.
remove_legacy_chat_data()


def chat_controller(request, handler):
    res = Response()
    cookies = request.cookies

    auth_token = cookies.get("auth_token", "")
    payload = verify_jwt(auth_token)
    user_id = payload.get("sub") if payload else None

    if not user_id: #chat routes remain limited to logged in users
        res.set_status(401, "Unauthorized")
        res.headers({"Content-Type": "text/html; charset=utf-8"})
        res.text("Unauthorized")
        handler.request.sendall(res.to_data())
        return

    # The old page still polls GET /api/chats once per second. Return an empty
    # list so that polling stays harmless while the plaintext collection is gone.
    if request.method == "GET" and request.path == "/api/chats":
        res.set_status(200, "OK")
        res.json({"messages": []})
        handler.request.sendall(res.to_data())
        return

    # SD-10 retires every write path from the old global chat API. Private chat
    # now uses /api/conversations/.../messages, whose body is encrypted by the
    # client. Do not read or parse request.body here; a readable message body
    # must never enter the old server-side chat path again.
    res.set_status(410, "Gone")
    res.json({"error": "Legacy chat API removed; use encrypted conversations"})
    handler.request.sendall(res.to_data())
    return
