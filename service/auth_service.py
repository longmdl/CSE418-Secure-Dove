from util.auth import extract_credentials, validate_password
from repository.auth_repository import get_user_profile_db, search_users_db, update_profile_db

import bcrypt


def get_user_profile(username):
    user_result = get_user_profile_db(username) #get user profile from db
    return user_result

def get_user_search(query):
    users_result = search_users_db(query) #pass the search query to db, will return a dict of user with that name
    if users_result is None: #if search query too long as indicated in auth_repository.py 
        return None
    result = []
    for user in users_result:
        result.append({
            "id": user.get("id"),
            "username": user.get("username")
        })
    return result

def update_user_profile(old_username, request):
    user_password_list = extract_credentials(request) #extract new username and password from request
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
    result = update_profile_db(old_username, new_username, password_bytes, salt)
    return result
