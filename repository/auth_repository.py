from util.database import user_collection


import bcrypt
import pyotp
import re 

def enable_otp_db(username):
    totp_secret = pyotp.random_base32()
    user_collection.update_one({"username": username}, {"$set": {"totp_secret": totp_secret}})
    return totp_secret

def register_user_db(user_id, username, password_bytes, salt):
    user_exist = user_collection.find_one({"username": username})

    if user_exist: #if username already exists return false
        return False

    user_collection.insert_one({
        "id": user_id,
        "username": username,
        "password": bcrypt.hashpw(password_bytes, salt),
        "totp_secret": None,
    })
    return True

def get_user_profile_db(username):
    user = user_collection.find_one({
        "username": username
    })
    if user: #if @me profile is found, return the username and id
        return {"username": user.get("username"),
                "id": user.get("id")}
    return None

def get_username_by_id_db(user_id):
    user = user_collection.find_one({"id": user_id})
    if user:
        return user.get("username")
    return None

def search_users_db(search):
    if len (search) > 32: #to prohibit searches len >= 33
        return None
    users = user_collection.find({"username": {"$regex": "^" + re.escape(search)}}) #case sensitive search
    return users

def update_profile_db(user_id, new_username, password_bytes, salt):
    user_exist = user_collection.find_one({"id": user_id})

    if not user_exist:
        return False

    username_taken = user_collection.find_one({"username": new_username})
    if username_taken and username_taken.get("id") != user_id:
        return False

    if password_bytes: #if password is included, update both username and password
        user_collection.update_one({"id": user_id},
        {"$set": {
        "username": new_username,
        "password": bcrypt.hashpw(password_bytes, salt)}})
    else:
        user_collection.update_one({"id": user_id}, #only update username
        {"$set": {
        "username": new_username}})
    return True
