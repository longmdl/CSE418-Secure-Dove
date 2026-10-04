import json
import uuid

from repository.chat_repository import post_chat_database, get_all_chat_database, patch_chat_database, delete_chat_database, update_chat_author_database
from repository.auth_repository import get_username_by_id_db


def post_chat(data, author_id):
    json_string = data.decode() #turns bytes into a json string
    json_chat_msg_dict = json.loads(json_string) #turns json string to python dict
    author_name = get_username_by_id_db(author_id)
    if author_name is None:
        return "user not found"
    if "content" in json_chat_msg_dict: #if content exists, handle it 
        chat_msg = json_chat_msg_dict.get("content", "")
        chat_msg_filtered = chat_msg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#x27;") #escaping html here
        author_name_filtered = author_name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#x27;")

        json_chat_msg_dict["content"] = chat_msg_filtered
        json_chat_msg_dict.update({"author": author_name_filtered}) #add author to dict
        json_chat_msg_dict.update({"author_id": author_id})
        json_chat_msg_dict.update({"id": str(uuid.uuid4())}) #add id to dict
        json_chat_msg_dict.update({"updated": False}) #add updated field to dict
        status = post_chat_database(json_chat_msg_dict) #send json dict to database
        return status
    return "missing message content" #if content is nonexistent

def update_chat_author(author_id, author_name):
    author_name_filtered = author_name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#x27;")
    update_chat_author_database(author_id, author_name_filtered)
    return

def get_all_chat(author_id):
    all_chat_cursor = get_all_chat_database()
    all_chat = []
    for chat in all_chat_cursor:
        chat.pop("_id", None)
        chat["owned"] = chat.pop("author_id", None) == author_id
        all_chat.append(chat)
    return {"messages": all_chat}

def patch_chat(message_id, data, author_id):
    json_string = data.decode() #turns bytes into a json string
    json_chat_msg_dict = json.loads(json_string) #turns json string to python dict
    if "content" in json_chat_msg_dict: #if content exists, handle it
        chat_msg = json_chat_msg_dict.get("content", "")
        chat_msg_filtered = chat_msg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#x27;") #escaping html here again

        msg_id_dict = {"id": message_id}
        updated_msg_dict = {"$set": {"content": chat_msg_filtered}}
        status = patch_chat_database(msg_id_dict, updated_msg_dict, author_id) #return true if succesful, false if not
        return status
    return "missing message content" #if content is nonexistent 

def delete_chat(message_id, author_id):
    msg_id_dict = {"id": message_id}
    status = delete_chat_database(msg_id_dict, author_id) #return true if successful, false if not
    return status
