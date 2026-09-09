import uuid

from util.response import Response
from service.chat_service import post_chat, get_all_chat, patch_chat, patch_emoji, delete_chat, delete_emoji, patch_nickname
from util.auth import verify_jwt



def chat_controller(request, handler):
    res = Response()
    path = request.path
    method = request.method
    request_body = request.body
    cookies = request.cookies

    user_id = cookies.get("session", "")
    user_new = False

    if user_id == "":
        user_id = str(uuid.uuid4())
        user_new = True

    author_name = "Guest " + user_id

    if method in ["POST", "PATCH", "DELETE"]: #authenticate user's token if they have one and extract their username
        auth_token = cookies.get("auth_token", "")
        payload = verify_jwt(auth_token)
        username = payload.get("username") if payload else None
        if username:
            author_name = username


    if method == "POST" and path == "/api/chats": #post a chat   
        post_chat(request_body, author_name) #send to post_chat in service layer
        if user_new:
            res.cookies({"session": user_id}) #if new user then give them a session cookie
        res.set_status(200, "OK")
        res.headers({"Content-Type": "text/html; charset=utf-8"})
        res.text("message sent")
        handler.request.sendall(res.to_data())
        return
    
    elif method == "GET" and path == "/api/chats": #get all chat messages
        all_chat = get_all_chat() #calls get all chat from service layer
        if all_chat:
            if user_new:
                res.cookies({"session": user_id}) #if new user then give them a session cookie
            res.set_status(200, "OK")
            res.headers({"Content-Type": "application/json"})
            res.json(all_chat)
            handler.request.sendall(res.to_data())
            return
        
    elif method == "PATCH" and path.startswith("/api/chats/"): #update a chat message
        extract = path.split("/")
        message_id = extract[3] #extract message id to be updated
        status = patch_chat(message_id,request_body, author_name) #send to patch_chat in service layer, if successful then it'll return true
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

    elif method == "PATCH" and path.startswith("/api/reaction/"): #update a chat message with a reaction
        extract = path.split("/")
        message_id = extract[3] #extract message id to be reacted to :)
        status = patch_emoji(message_id,request_body, author_name) #send to patch_emoji in service layer, if successful then it'll return true
        if status:
            res.set_status(200, "OK")
            res.headers({"Content-Type": "text/html; charset=utf-8"})
            res.text("emoji added successfully")
            handler.request.sendall(res.to_data())
            return
        else:
            res.set_status(403, "Forbidden")
            res.headers({"Content-Type": "text/html; charset=utf-8"})
            res.text("you cant react with the same emoji twice")
            handler.request.sendall(res.to_data())
            return
        
    elif method == "PATCH" and path == "/api/nickname": #update a chat message with a nickname
        status = patch_nickname(request_body, author_name) #send to patch_nickname in service layer, if successful then it'll return true
        if status:
            res.set_status(200, "OK")
            res.headers({"Content-Type": "text/html; charset=utf-8"})
            res.text("nicknames added successfully")
            handler.request.sendall(res.to_data())
            return
        else:
            res.set_status(403, "Forbidden")
            res.headers({"Content-Type": "text/html; charset=utf-8"})
            res.text("something went wrong with updating your nickname")
            handler.request.sendall(res.to_data())
        
    elif method == "DELETE" and path.startswith("/api/reaction/"): #delete a reaction from a chat message
        extract = path.split("/")
        message_id = extract[3] #extract message id where the emoji needs to be deleted
        status = delete_emoji(message_id,request_body, author_name) #send to delete_emoji in service layer, if successful then it'll return true
        if status:
            res.set_status(200, "OK")
            res.headers({"Content-Type": "text/html; charset=utf-8"})
            res.text("emoji delete successfully")
            handler.request.sendall(res.to_data())
            return
        else:
            res.set_status(403, "Forbidden")
            res.headers({"Content-Type": "text/html; charset=utf-8"})
            res.text("no permission to delete this emoji")
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

