import jwt
import datetime
import uuid
import bcrypt
import pyotp

from util.response import Response
from util.auth import extract_credentials, validate_password
from util.database import user_collection
from repository.auth_repository import register_user_db
from repository.login_failure_repository import is_locked_out_db, record_failed_login_db, reset_failed_logins_db


with open("/root/keys/jwt_private.pem", "rb") as f: 
    PRIVATE_KEY = f.read()

def issue_jwt(user_id, username):
    now = datetime.datetime.utcnow()
    payload = {
        "sub": user_id,
        "username": username,
        "iat": now,
        "exp": now + datetime.timedelta(seconds=3600),
    }
    return jwt.encode(payload, PRIVATE_KEY, algorithm="RS256")


def auth_controller(request, handler):
    res = Response()
    path = request.path
    method = request.method
    cookies = request.cookies

    if method == "POST" and path == "/register":
        credentials = extract_credentials(request)
        username = credentials[0]
        password = credentials[1]
        
        if not validate_password(password):
            res.set_status(400, "Bad Request")
            res.text("user failed to register")
            handler.request.sendall(res.to_data())
            return

        user_id = str(uuid.uuid4())
        salt = bcrypt.gensalt()
        success = register_user_db(user_id, username, password.encode(), salt)

        if not success:
            res.set_status(400, "Bad Request")
            res.text("user failed to register")
            handler.request.sendall(res.to_data())
            return

        token = issue_jwt(user_id, username)
        res.set_status(200, "OK")
        res.text("user registered successfully")
        res.auth_token(token, 3600)
        handler.request.sendall(res.to_data())
        return

    if method == "POST" and path == "/login":
        credentials = extract_credentials(request)
        username = credentials[0]
        password = credentials[1]
        totp_code = credentials[2] if len(credentials) > 2 else None

        if is_locked_out_db(username): #SD-12: same generic 429 as nginx, whether or not the account exists
            res.set_status(429, "Too Many Requests")
            res.text("too many requests, try again later")
            handler.request.sendall(res.to_data())
            return

        user = user_collection.find_one({"username": username})
        if not user:
            record_failed_login_db(username) #unknown names count too, so a lockout doesn't reveal which accounts exist
            res.set_status(400, "Bad Request")
            res.text("user failed to login")
            handler.request.sendall(res.to_data())
            return

        if not bcrypt.checkpw(password.encode(), user["password"]):
            record_failed_login_db(username)
            res.set_status(400, "Bad Request")
            res.text("user failed to login")
            handler.request.sendall(res.to_data())
            return

        totp_secret = user.get("totp_secret")
        if totp_secret:
            if not totp_code:
                res.set_status(401, "Unauthorized")
                res.text("2FA code required")
                handler.request.sendall(res.to_data())
                return
            if not pyotp.TOTP(totp_secret).verify(totp_code):
                record_failed_login_db(username)
                res.set_status(400, "Bad Request")
                res.text("user failed to login")
                handler.request.sendall(res.to_data())
                return

        reset_failed_logins_db(username) #a successful login clears the failure count
        token = issue_jwt(user["id"], user["username"])
        res.set_status(200, "OK")
        res.text("user logged in successfully")
        res.auth_token(token, 3600)
        handler.request.sendall(res.to_data())
        return

    if method == "GET" and path == "/logout":
        res.set_status(302, "Found")
        res.headers({"Location": "/"})
        res.auth_token("", 0)
        handler.request.sendall(res.to_data())
        return