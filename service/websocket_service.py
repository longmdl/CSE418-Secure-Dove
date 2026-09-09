import json
import uuid
from util.websockets import generate_ws_frame
from repository.drawing_repository import get_all_drawings_db, insert_drawing_db

connected_users = {} #handler -> username
connection_ids = {} #handler -> uuid (socket_id)
rooms = {} #room_id -> {"name": room_name, "participants": {handler -> socket_id}}

def create_room(room_id, room_name):
    rooms[room_id] = {"name": room_name, "participants": {}}

def register(handler, username):
    connected_users[handler] = username
    connection_ids[handler] = str(uuid.uuid4())
    broadcast_user_list()


def unregister(handler):
    socket_id = connection_ids.get(handler)
    for room_data in rooms.items():
        if handler in room_data["participants"]:
            del room_data["participants"][handler]

            left_msg = {"messageType": "user_left", "socketId": socket_id} #announcing the departure to everyone
            for participant_handler in list(room_data["participants"].keys()):
                send(participant_handler, json.dumps(left_msg))
            break 

    if handler in connection_ids:
        del connection_ids[handler]

    if handler in connected_users:
        del connected_users[handler]
        broadcast_user_list()


def send_initial_state(handler):
    strokes = get_all_drawings_db()
    if strokes:
        msg = json.dumps({"messageType": "init_strokes", "strokes": strokes})
        send(handler, msg)


def handle_message(handler, message_data):
    message_type = message_data.get("messageType")

    if message_type == "echo_client":
        handle_echo(handler, message_data)
    elif message_type == "drawing":
        handle_drawing(message_data)

    elif message_type == "get_calls":
        calls_list = [{"id": room_id, "name": room_data["name"]} for room_id, room_data in rooms.items()]
        send(handler, json.dumps({"messageType": "call_list", "calls": calls_list}))
        
    elif message_type == "join_call":
        call_id = message_data.get("callId")
        if call_id in rooms:
            room = rooms[call_id]
            my_socket_id = connection_ids[handler]
            my_username = connected_users[handler]
            
            participants_list = []
            for participant_handler, participant_socket_id in room["participants"].items(): 
                participants_list.append({
                    "socketId": participant_socket_id,
                    "username": connected_users[participant_handler]}) #gather all existing participants
            
            send(handler, json.dumps({
                "messageType": "existing_participants",
                "participants": participants_list})) #send existing participants to the fella that just joined
            
            
            joined_msg = json.dumps({
                "messageType": "user_joined",
                "socketId": my_socket_id,
                "username": my_username}) #annouce ppl you have joined
            
            for participant_handler in list(room["participants"].keys()):
                send(participant_handler, joined_msg)
                
            room["participants"][handler] = my_socket_id #add you to room
            
            send(handler, json.dumps({"messageType": "call_info", "name": room["name"]})) #send the name of the room to the fella that just joined

    elif message_type in ["offer", "answer", "ice_candidate"]:
        target_socket_id = message_data.get("socketId") #who this is meant for

        target_handler = None
        for current_handler, socket_id in connection_ids.items():
            if socket_id == target_socket_id:
                target_handler = current_handler
                break
                
        if target_handler:
            message_data["socketId"] = connection_ids[handler] #swap target id with sender id
            message_data["username"] = connected_users[handler] #swap target username with sender username
            send(target_handler, json.dumps(message_data))

def handle_echo(handler, message_data):
    reply = {"messageType": "echo_server", "text": message_data.get("text", "")}
    send(handler, json.dumps(reply))


def handle_drawing(message_data):
    insert_drawing_db(message_data.copy())
    broadcast(message_data)


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