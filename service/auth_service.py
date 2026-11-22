from util.auth import extract_credentials, validate_password
from repository.auth_repository import get_user_profile_db, search_users_db, update_profile_db, get_user_by_id_db
from repository.login_failure_repository import is_locked_out_db, record_failed_login_db, reset_failed_logins_db
from service.chat_service import update_chat_author

import bcrypt
import pyotp

#results of check_current_totp
TOTP_OK = "ok"
TOTP_MISSING = "missing"
TOTP_INVALID = "invalid"
TOTP_LOCKED = "locked"


def check_current_totp(user_id, totp_code):
    #step-up check for sensitive actions (changing the password, regenerating 2FA),
    #so someone at an unlocked session also needs the authenticator.
    #accounts without 2FA have nothing to check against, so they pass with no code.
    user = get_user_by_id_db(user_id)
    if not user:
        return TOTP_INVALID

    totp_secret = user.get("totp_secret")
    if not totp_secret:
        return TOTP_OK

    #wrong codes share the login lockout counter: it's the same secret being guessed,
    #so a session holder gets the same 5 tries per 5 minutes as someone at the login page
    username = user.get("username")
    if is_locked_out_db(username):
        return TOTP_LOCKED
    if not totp_code:
        return TOTP_MISSING
    if not pyotp.TOTP(totp_secret).verify(totp_code):
        record_failed_login_db(username)
        return TOTP_INVALID

    reset_failed_logins_db(username)
    return TOTP_OK


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

def update_user_profile(user_id, request):
    user_password_list = extract_credentials(request) #extract new username and password from request
    new_username = user_password_list[0]
    new_password = user_password_list[1]

    if new_password == "": #empty password will only update the username
        result = update_profile_db(user_id, new_username, None, None)
        if result:
            update_chat_author(user_id, new_username)
        return result

    password_valid = validate_password(new_password) #validate new password
    if not password_valid:
        return False

    password_bytes = new_password.encode()
    salt = bcrypt.gensalt() #sprinkle some more salt
    result = update_profile_db(user_id, new_username, password_bytes, salt)
    if result:
        update_chat_author(user_id, new_username)
    return result
