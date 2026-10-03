import json
import uuid

from repository.chat_repository import post_chat_database, get_all_chat_database, patch_chat_database, delete_chat_database


def post_chat(data, author_name):
    json_string = data.decode() #turns bytes into a json string
    json_chat_msg_dict = json.loads(json_string) #turns json string to python dict
    if "content" in json_chat_msg_dict: #if content exists, handle it 
        chat_msg = json_chat_msg_dict.get("content", "")
        chat_msg_filtered = chat_msg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") #escaping html here

        json_chat_msg_dict["content"] = chat_msg_filtered
        json_chat_msg_dict.update({"author": author_name}) #add author to dict
        json_chat_msg_dict.update({"id": str(uuid.uuid4())}) #add id to dict
        json_chat_msg_dict.update({"updated": False}) #add updated field to dict
        status = post_chat_database(json_chat_msg_dict) #send json dict to database
        return status
    return "missing message content" #if content is nonexistent

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
    if "content" in json_chat_msg_dict: #if content exists, handle it
        chat_msg = json_chat_msg_dict.get("content", "")
        chat_msg_filtered = chat_msg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") #escaping html here again

        json_chat_msg_dict["content"] = chat_msg_filtered
        msg_id_dict = {"id": message_id}
        updated_msg_dict = {"$set": json_chat_msg_dict}
        status = patch_chat_database(msg_id_dict, updated_msg_dict, author_name) #return true if succesful, false if not
        return status
    return "missing message content" #if content is nonexistent 

def delete_chat(message_id, author_name):
    msg_id_dict = {"id": message_id}
    status = delete_chat_database(msg_id_dict, author_name) #return true if successful, false if not
    return status
