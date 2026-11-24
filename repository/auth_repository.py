from util.database import user_collection
from pymongo.errors import DuplicateKeyError 

import bcrypt
import pyotp
import re 

#from mongodb docs:
#user_collection.createIndex( { "username": 1 }, { unique: true } ) -> must be translated into python w/ pymongo
user_collection.create_index("username", unique=True) #for later recognition of duplicatekeyerror, from mongodbdocs

def enable_otp_db(user_id):
    #the new secret waits in pending_totp_secret until the user proves they saved it
    #(confirm_pending_totp_db). until then login keeps using the old totp_secret, or none
    totp_secret = pyotp.random_base32()
    user_collection.update_one({"id": user_id}, {"$set": {"pending_totp_secret": totp_secret}})
    return totp_secret

def confirm_pending_totp_db(user_id, pending_secret):
    #matching on the secret that was checked means a regenerate in between (a newer
    #pending secret) can't be switched on by a code from the older one
    result = user_collection.update_one(
        {"id": user_id, "pending_totp_secret": pending_secret},
        {"$set": {"totp_secret": pending_secret}, "$unset": {"pending_totp_secret": ""}})
    return result.modified_count == 1

def get_user_by_id_db(user_id):
    return user_collection.find_one({"id": user_id})

def register_user_db(user_id, username, password_bytes, salt):
    user_exist = user_collection.find_one({"username": username})

    if user_exist: #if username already exists return false
        return False
    try:
        user_collection.insert_one({
            "id": user_id,
            "username": username,
            "password": bcrypt.hashpw(password_bytes, salt),
            "totp_secret": None,
            })
        return True
    except DuplicateKeyError:
        return False

def get_user_profile_db(username):
    user = user_collection.find_one({
        "username": username
    })
    if user: #if @me profile is found, return the username and id
        return {"username": user.get("username"),
                "id": user.get("id"),
                "totp_enabled": bool(user.get("totp_secret"))} #so settings knows to ask for the current code
    return None

def get_username_by_id_db(user_id):
    user = user_collection.find_one({"id": user_id})
    if user:
        return user.get("username")
    return None

def search_users_db(search):
    if len (search) > 32: #to prohibit searches len >= 33
        return None
    users = user_collection.find({"username": {"$regex": "^" + re.escape(search)}}).limit(20) #case sensitive search
    return users

def update_profile_db(user_id, new_username, password_bytes, salt):
    user_exist = user_collection.find_one({"id": user_id})

    if not user_exist:
        return False

    username_taken = user_collection.find_one({"username": new_username})
    if username_taken and username_taken.get("id") != user_id:
        return False
    try:
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
    
    except DuplicateKeyError: #same for register, but now a duplicate username will be caught as well
        return False 

