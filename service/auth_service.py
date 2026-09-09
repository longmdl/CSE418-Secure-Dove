from util.auth import extract_credentials, validate_password
from repository.auth_repository import register_user_db, login_user_db, invalidate_token_db, get_user_profile_db, search_users_db, update_profile_db

import bcrypt
import uuid

def register_user(request):
    user_password_list =  extract_credentials(request)
    username = user_password_list[0]
    password = user_password_list[1]

    password_valid = validate_password(password)
    if not password_valid:
        return False
    
    else:
        password_bytes = password.encode() 

        salt = bcrypt.gensalt() #sprinkling some salt

        user_id = str(uuid.uuid4()) #generate unique user_id
        result = register_user_db(user_id,username,password_bytes,salt)
    return result

def login_user(request):
    user_password_list =  extract_credentials(request)
    username = user_password_list[0]
    password = user_password_list[1] #extract password
    totp_code = None 
    
    if len(user_password_list) > 2:
        totp_code = user_password_list[2] 
    else:
        None 

    auth_token = login_user_db(username, password, totp_code) #grants an auth token if succesful

    if not auth_token == "": #if successful return auth token
        return auth_token
    else:
        return False #return false if failed
    
def logout_user(auth_token):
    invalidate_token_db(auth_token) #remove auth token from db
    return

def get_user_profile(username):
    user_result = get_user_profile_db(username) #get user profile from db
    return user_result

def get_user_search(query):
    users_result = search_users_db(query) #pass the search query to db, will return a dict of user with that name
    result = []
    for user in users_result:
        result.append({
            "id": user.get("id"),
            "username": user.get("username")
        })
    return result

def update_user_profile(old_username,request):
    user_password_list =  extract_credentials(request) #extract new username and password from request
    new_username = user_password_list[0]
    new_password = user_password_list[1]

    if new_password == "": #empty password will only update the username
        result = update_profile_db(old_username, new_username, None, None)
        return result

    password_valid = validate_password(new_password) #validate new password
    if not password_valid:
        return False
    
    password_bytes = new_password.encode()
    salt = bcrypt.gensalt() #sprinkle some more salt
    result = update_profile_db(old_username,new_username,password_bytes,salt)
    return result





