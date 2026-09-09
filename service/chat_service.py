import json
import uuid

from repository.chat_repository import post_chat_database, get_all_chat_database, patch_chat_database, delete_chat_database, patch_emoji_database, delete_emoji_database, patch_nickname_database
from repository.auth_repository import get_avatar_url_db


def post_chat(data, author_name):
    json_string = data.decode() #turns bytes into a json string
    json_chat_msg_dict = json.loads(json_string) #turns json string to python dict

    chat_msg= json_chat_msg_dict.get("content", "")
    chat_msg_filtered = chat_msg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") #escaping html here

    avatar_url = get_avatar_url_db(author_name)

    json_chat_msg_dict["content"] = chat_msg_filtered
    json_chat_msg_dict.update({"author": author_name}) #add author to dict
    json_chat_msg_dict.update({"id" : str(uuid.uuid4())}) #add id to dict
    json_chat_msg_dict.update({"updated" : False}) #add updated field to dict
    json_chat_msg_dict.update({"reactions": {}}) #add reactions field to dict
    json_chat_msg_dict.update({"nickname": ""}) #add nickname field to dict
    json_chat_msg_dict.update({"imageURL": avatar_url}) #add avatar url field to dict
    status = post_chat_database(json_chat_msg_dict, author_name) #send json dict to database
    return status

def get_all_chat():
    all_chat_cursor = get_all_chat_database()
    all_chat = []
    for chat in all_chat_cursor:
        chat.pop("_id", None)
        all_chat.append(chat)
    return {"messages": all_chat}

def patch_chat(message_id, data, author_name):
    json_string = data.decode() #turns bytes into a json string
    json_chat_msg_dict = json.loads(json_string) #turns json string to python dict

    chat_msg= json_chat_msg_dict.get("content", "")
    chat_msg_filtered = chat_msg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") #escaping html here again

    json_chat_msg_dict["content"] = chat_msg_filtered
    msg_id_dict = {"id": message_id}
    updated_msg_dict = {"$set": json_chat_msg_dict}
    status = patch_chat_database(msg_id_dict,updated_msg_dict, author_name) #return true if succesful, false if not
    return status

def patch_emoji(message_id, data, author_name):
    json_string = data.decode() #turns bytes into a json string
    json_emoji_dict = json.loads(json_string) #turns json string to python dict

    msg_id_dict = {"id": message_id}
    status = patch_emoji_database(msg_id_dict, json_emoji_dict["emoji"], author_name) #return true if succesful, false if not
    return status

def patch_nickname(data, author_name):
    json_string = data.decode() #turns bytes into a json string
    json_nickname_dict = json.loads(json_string) #turns json string to python dict

    status = patch_nickname_database(json_nickname_dict["nickname"], author_name) #return true if succesful, false if not
    return status

def delete_chat(message_id, author_name):
    msg_id_dict = {"id": message_id}
    status = delete_chat_database(msg_id_dict, author_name) #return true if successful, false if not
    return status

def delete_emoji(message_id, data, author_name):
    json_string = data.decode() #turns bytes into a json string
    json_emoji_dict = json.loads(json_string) #turns json string to python dict

    msg_id_dict = {"id": message_id}
    status = delete_emoji_database(msg_id_dict, json_emoji_dict["emoji"], author_name) #return true if successful, false if not
    return status

