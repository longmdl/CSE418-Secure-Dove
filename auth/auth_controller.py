import jwt
import datetime
import uuid
import bcrypt
import pyotp

from util.response import Response
from util.auth import extract_credentials, validate_password
from util.database import user_collection
from repository.auth_repository import register_user_db


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

        user = user_collection.find_one({"username": username})
        if not user:
            res.set_status(400, "Bad Request")
            res.text("user failed to login")
            handler.request.sendall(res.to_data())
            return

        if not bcrypt.checkpw(password.encode(), user["password"]):
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
                res.set_status(400, "Bad Request")
                res.text("user failed to login")
                handler.request.sendall(res.to_data())
                return

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