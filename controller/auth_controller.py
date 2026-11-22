from util.response import Response
from service.auth_service import get_user_profile, get_user_search, update_user_profile, check_current_totp, confirm_new_totp, TOTP_OK, TOTP_MISSING, TOTP_LOCKED, TOTP_NO_PENDING
from repository.auth_repository import enable_otp_db
from util.auth import verify_jwt, extract_credentials, extract_totp_code


def send_totp_failure(res, handler, result):
    if result == TOTP_LOCKED: #same generic 429 as nginx and the login lockout
        res.set_status(429, "Too Many Requests")
        res.text("too many requests, try again later")
    elif result == TOTP_MISSING:
        res.set_status(403, "Forbidden")
        res.text("2FA code required")
    elif result == TOTP_NO_PENDING:
        res.set_status(400, "Bad Request")
        res.text("no new 2FA secret to confirm, regenerate 2FA first")
    else:
        res.set_status(403, "Forbidden")
        res.text("invalid 2FA code")
    handler.request.sendall(res.to_data())


def auth_controller(request, handler):
    res = Response()
    path = request.path
    method = request.method
    cookies = request.cookies

    if method == "GET" and path == "/api/users/@me": #get the user current profile
        auth_token = cookies.get("auth_token", "")

        payload = verify_jwt(auth_token) #validate token and get username
        username = payload.get("username") if payload else None

        if username:
            user_data = get_user_profile(username)
            if not user_data:
                res.set_status(401, "Unauthorized")
                res.json({})
                handler.request.sendall(res.to_data())
                return
            res.set_status(200, "OK")
            res.json(user_data)
            handler.request.sendall(res.to_data())
            return
        res.set_status(401, "Unauthorized") #not logged in
        res.json({})
        handler.request.sendall(res.to_data())
        return

    if method == "GET" and path.startswith("/api/users/search"):
        payload = verify_jwt(cookies.get("auth_token", ""))
        if not payload: #search is for logged in users only
            res.set_status(401, "Unauthorized")
            res.json({"users": []})
            handler.request.sendall(res.to_data())
            return
        
        query = ""
        if "?" in request.path: #check if theres ? in request path
            query_list = request.path.split("?", 1)
            query_string = query_list[1]
            user_parts = query_string.split('=', 1)

            if len(user_parts) == 2 and user_parts[0] == "user":
                query = user_parts[1] #extract the search query

        if not query.strip(): #.strip() trims whitespace in case an "empty" query is all whitespace
            res.set_status(200, "OK")
            res.json({"users": []}) #send back empty list if query is empty
            handler.request.sendall(res.to_data())
            return

        users = get_user_search(query)
        if users is None: #if search is too long (>=33)
            res.set_status(400, "Bad Request")
            res.json({"users": []}) #send back empty users list
            handler.request.sendall(res.to_data())
            return 
            
        res.set_status(200, "OK")
        res.json({"users": users}) #send back users list
        handler.request.sendall(res.to_data())
        return

    if method == "POST" and path == "/api/users/settings": #update current user profile
        auth_token = cookies.get("auth_token", "")
        payload = verify_jwt(auth_token)
        user_id = payload.get("sub") if payload else None

        if not user_id:
            res.set_status(401, "Unauthorized") #not logged in
            res.text("Must be logged in")
            handler.request.sendall(res.to_data())
            return

        credentials = extract_credentials(request)
        if credentials[1] != "": #a new password needs the current 2FA code, a username-only change doesn't
            totp_code = credentials[2] if len(credentials) > 2 else None
            totp_result = check_current_totp(user_id, totp_code)
            if totp_result != TOTP_OK:
                send_totp_failure(res, handler, totp_result)
                return

        result = update_user_profile(user_id, request) #pass it on to service layer
        if result:
            res.set_status(200, "OK")
            res.text("information updated succesfully")
            handler.request.sendall(res.to_data())
            return
        else:
            res.set_status(400, "Bad Request")
            res.text("failed to update information")
            handler.request.sendall(res.to_data())
            return

    if method == "POST" and path == "/api/totp/enable":
        auth_token = cookies.get("auth_token", "")
        payload = verify_jwt(auth_token)
        user_id = payload.get("sub") if payload else None #id, not username: the token's username goes stale after a rename
        if not user_id:
            res.set_status(401, "Unauthorized") #not logged in
            res.json({})
            handler.request.sendall(res.to_data())
            return

        totp_result = check_current_totp(user_id, extract_totp_code(request)) #replacing 2FA needs the current 2FA
        if totp_result != TOTP_OK:
            send_totp_failure(res, handler, totp_result)
            return

        totp_secret = enable_otp_db(user_id) #new secret, pending until /api/totp/confirm
        res.set_status(200, "OK")
        res.json({"secret": totp_secret}) #send to front end to generate qr code
        handler.request.sendall(res.to_data())
        return

    if method == "POST" and path == "/api/totp/confirm": #switch on the secret from /api/totp/enable
        auth_token = cookies.get("auth_token", "")
        payload = verify_jwt(auth_token)
        user_id = payload.get("sub") if payload else None
        if not user_id:
            res.set_status(401, "Unauthorized") #not logged in
            res.json({})
            handler.request.sendall(res.to_data())
            return

        totp_result = confirm_new_totp(user_id, extract_totp_code(request)) #code must come from the NEW authenticator entry
        if totp_result != TOTP_OK:
            send_totp_failure(res, handler, totp_result)
            return

        res.set_status(200, "OK")
        res.text("2FA updated")
        handler.request.sendall(res.to_data())
        return
