from util.response import Response
from service.chat_service import post_chat, get_all_chat, patch_chat, delete_chat
from util.auth import verify_jwt


def chat_controller(request, handler):
    res = Response()
    path = request.path
    method = request.method
    request_body = request.body
    cookies = request.cookies

    auth_token = cookies.get("auth_token", "")
    payload = verify_jwt(auth_token)
    author_name = payload.get("username") if payload else None

    if not author_name: #chat is for logged in users only, there are no guests
        res.set_status(401, "Unauthorized")
        res.headers({"Content-Type": "text/html; charset=utf-8"})
        res.text("Unauthorized")
        handler.request.sendall(res.to_data())
        return

    if method == "POST" and path == "/api/chats": #post a chat
        post_chat(request_body, author_name) #send to post_chat in service layer
        res.set_status(200, "OK")
        res.headers({"Content-Type": "text/html; charset=utf-8"})
        res.text("message sent")
        handler.request.sendall(res.to_data())
        return

    elif method == "GET" and path == "/api/chats": #get all chat messages
        all_chat = get_all_chat() #calls get all chat from service layer
        res.set_status(200, "OK")
        res.headers({"Content-Type": "application/json"})
        res.json(all_chat)
        handler.request.sendall(res.to_data())
        return

    elif method == "PATCH" and path.startswith("/api/chats/"): #update a chat message
        extract = path.split("/")
        message_id = extract[3] #extract message id to be updated
        status = patch_chat(message_id, request_body, author_name) #send to patch_chat in service layer, if successful then it'll return true
        if status:
            res.set_status(200, "OK")
            res.headers({"Content-Type": "text/html; charset=utf-8"})
            res.text("message updated successfully")
            handler.request.sendall(res.to_data())
            return
        else:
            res.set_status(403, "Forbidden")
            res.headers({"Content-Type": "text/html; charset=utf-8"})
            res.text("user lacks permission to update")
            handler.request.sendall(res.to_data())
            return

    elif method == "DELETE" and path.startswith("/api/chats/"): #delete a chat message
        extract = path.split("/")
        message_id = extract[3] #extract message id to be deleted
        status = delete_chat(message_id, author_name) #send to delete chat, if succesful then it'll return true
        if status:
            res.set_status(200, "OK")
            res.headers({"Content-Type": "text/html; charset=utf-8"})
            res.text("message deleted successfully")
            handler.request.sendall(res.to_data())
            return
        else:
            res.set_status(403, "Forbidden")
            res.headers({"Content-Type": "text/html; charset=utf-8"})
            res.text("user lacks permission to delete")
            handler.request.sendall(res.to_data())
            return

    else:
        res.set_status(404, "Not Found")
        res.headers({"Content-Type": "text/html; charset=utf-8"})
        res.text("Something went wrong")
        handler.request.sendall(res.to_data())
        return
