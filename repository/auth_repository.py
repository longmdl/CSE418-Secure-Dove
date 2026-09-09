from util.database import user_collection


import bcrypt
import uuid
import hashlib
import pyotp

def oauth_login_db(username):
    user = user_collection.find_one({"username": username}) #find the user with their github acc username
    
    if not user: #if user not found, create new user
        user_id = str(uuid.uuid4())
        user_collection.insert_one({
            "id": user_id,
            "username": username,
            "password": None,
            "auth_token": None,
            "totp_secret": None,
            "imageURL": None,
        })
    
    auth_token = str(uuid.uuid4()) #generate auth token
    hash_auth_token = hashlib.sha256(auth_token.encode('utf-8')).hexdigest()
    user_collection.update_one({"username": username}, {"$set": {"auth_token": hash_auth_token}})
    return auth_token

def login_user_db(username, password, totp_code = None):
    user = user_collection.find_one({
        "username": username
    }) #find the user with their username

    if user:
        hashed_password = user.get("password")
        password_bytes = password.encode('utf-8')
        is_valid = bcrypt.checkpw(password_bytes, hashed_password) #check if the password match
        user_id = user.get("id")

        if is_valid:
            totp_secret = user.get("totp_secret") #if password is valid, we will check if they enabled otp

            if totp_secret: #if totp_secret exists means they enabled 2fa
                if not totp_code: #if there isnt a otp code, return ""
                    return "missing 2fa code"
                totp = pyotp.TOTP(totp_secret)
                if not totp.verify(totp_code): #wrong otp code, return ""
                    return ""
            
            auth_token = str(uuid.uuid4())
            hash_auth_token = hashlib.sha256(auth_token.encode('utf-8')).hexdigest()
            user_collection.update_one({"id": user_id},{"$set":{"auth_token": hash_auth_token}})
            return auth_token
        else:
            return ""
    return ""

def enable_otp_db(username):
    totp_secret = pyotp.random_base32()
    user_collection.update_one({"username":username},{"$set": {"totp_secret": totp_secret}})
    return totp_secret

def register_user_db(user_id,username,password_bytes,salt):
    user_exist = user_collection.find_one({"username": username})

    if user_exist: #if username already exists return false
        return False

    user_collection.insert_one({
        "id": user_id,
        "username": username,
        "password": bcrypt.hashpw(password_bytes, salt),
        "auth_token": None,
        "totp_secret": None,
        "imageURL": None,
    })
    return True

def invalidate_token_db(token):
    hash_token = hashlib.sha256(token.encode('utf-8')).hexdigest() #hash the auth token and store it in db
    user_collection.update_one({"auth_token": hash_token}, {"$set": {"auth_token": None}})

def validate_token_db(token):
    if not token:
        return None
    hash_token = hashlib.sha256(token.encode('utf-8')).hexdigest() #hash the user token and check with the db, if successful then return their username
    user = user_collection.find_one({"auth_token": hash_token})
    if user:
        return user.get("username")
    
def get_user_profile_db(username):
    user = user_collection.find_one({
        "username": username
    })
    if user: #if @me profile is found, return the username and id
        return {"username": user.get("username"),
                "id": user.get("id")}
    return None

def search_users_db(search):
    users = user_collection.find({"username": {"$regex": "^" + search}}) #case sensitive search
    return users

def update_profile_db(old_username,new_username,password_bytes,salt):
    user_exist = user_collection.find_one({"username": old_username}) #find the user using their old_username

    if not user_exist:
        return False

    if password_bytes: #if password is included, update both username and password
        user_collection.update_one({"username": old_username},
        {"$set":{
        "username": new_username,
        "password": bcrypt.hashpw(password_bytes, salt)}}) 
    else:
        user_collection.update_one({"username": old_username}, #only update username
        {"$set":{
        "username": new_username}})
    return True

def update_avatar_url_db(username, avatar_url):
    user_collection.update_one({"username": username}, {"$set": {"avatar_url": avatar_url}})

def get_avatar_url_db(username):
    user = user_collection.find_one({"username": username})
    if user:
        return user.get("avatar_url")
    return None

    


