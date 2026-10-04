from util.database import chat_collection

def post_chat_database(data):
    chat_collection.insert_one(data) #add message to db
    return

def get_all_chat_database():
    all_chat_cursor = chat_collection.find() #get all messages from db
    return all_chat_cursor

def update_chat_author_database(author_id, author_name):
    chat_collection.update_many({"author_id": author_id}, {"$set": {"author": author_name}})
    return

def patch_chat_database(id, updated_data, author_id):
    current_message = chat_collection.find_one(id)
    if current_message is None: #if None should be separate for separate return statuses 
        return None
    if current_message.get("author_id") != author_id: #if not the same author then you cant patch
        return False

    updated_data["$set"]["updated"] = True
    chat_collection.update_one(id, updated_data) #update message from db
    return True

def delete_chat_database(id, author_id):
    current_message = chat_collection.find_one(id)
    if current_message is None:
        return None
    if current_message.get("author_id") != author_id: #if not the same author then you cant delete
        return False

    chat_collection.delete_one(id) #delete message from db
    return True
