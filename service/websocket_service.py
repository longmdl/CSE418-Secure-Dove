import json
import uuid
from util.websockets import generate_ws_frame

connected_users = {} #handler -> username
connection_ids = {} #handler -> uuid (socket_id)


def register(handler, username):
    connected_users[handler] = username
    connection_ids[handler] = str(uuid.uuid4())
    broadcast_user_list()


def unregister(handler):
    if handler in connection_ids:
        del connection_ids[handler]

    if handler in connected_users:
        del connected_users[handler]
        broadcast_user_list()


def handle_message(handler, message_data):
    message_type = message_data.get("messageType")
    #no message types are handled yet, encrypted message relay lands here
    return message_type


def broadcast_user_list():
    users = [{"username": u} for u in connected_users.values()]
    broadcast({"messageType": "active_users_list", "users": users})


def broadcast(message_dict):
    frame = generate_ws_frame(json.dumps(message_dict).encode())
    for handler in list(connected_users): #copy keys to avoid mutation during iteration
        send_raw(handler, frame)


def send(handler, message):
    send_raw(handler, generate_ws_frame(message.encode()))


def send_raw(handler, frame):
    try:
        handler.request.sendall(frame)
    except Exception:
        pass
