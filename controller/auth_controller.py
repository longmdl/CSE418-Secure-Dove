from util.response import Response
from service.auth_service import register_user, login_user, logout_user, get_user_profile, get_user_search, update_user_profile
from repository.auth_repository import enable_otp_db, oauth_login_db, update_avatar_url_db, get_avatar_url_db
from util.multipart import parse_multipart
from util.auth import verify_jwt

import uuid
import requests as requests
import os

def auth_controller(request, handler):
    res = Response()
    path = request.path
    method = request.method
    body = request.body
    cookies = request.cookies

    if method == "POST" and path == "/register": #doesnt support jwt
        status = register_user(request)
        if status:
            res.set_status(200, "OK")
            res.headers({"Content-Type": "text/html; charset=utf-8"})
            res.text("user registered successfully")
            handler.request.sendall(res.to_data())
            return
        else:
            res.set_status(400, "Bad Request")
            res.headers({"Content-Type": "text/html; charset=utf-8"})
            res.text("user failed to register")
            handler.request.sendall(res.to_data())
            return
        
    if method == "POST" and path == "/login": #doesnt support jwt
        auth_token = login_user(request) #login user will return an auth token if succesful, if not its a bad request
        if auth_token == "missing 2fa code":
            res.set_status(401, "Unauthorized")
            res.text("2FA code required")
            handler.request.sendall(res.to_data())
            return
        if auth_token:
            res.set_status(200, "OK")
            res.headers({"Content-Type": "text/html; charset=utf-8"})
            res.text("user logged in successfully")
            res.auth_token(auth_token, 3600) #grant them the auth token in their cookies
            handler.request.sendall(res.to_data())
            return
        else:
            res.set_status(400, "Bad Request")
            res.headers({"Content-Type": "text/html; charset=utf-8"})
            res.text("user failed to login")
            handler.request.sendall(res.to_data())
            return

    if method == "GET" and path == "/logout": #doesnt support jwt
        auth_token = cookies.get("auth_token", "")
        logout_user(auth_token) #pass on to service and remove their auth token in db
        res.set_status(302, "Found")
        res.headers({"Location": "/"}) #redirect to homepage
        res.auth_token("", 0) #revoke their auth token by setting maxage to 0
        handler.request.sendall(res.to_data())
        return
    
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
            avatar_url = get_avatar_url_db(username)
            user_data["imageURL"] = avatar_url
            res.json(user_data)
            handler.request.sendall(res.to_data())
            return
        res.set_status(401,"Unauthorized") #not logged in
        res.json({})
        handler.request.sendall(res.to_data())
        return
    
    if method == "GET" and path.startswith("/api/users/search"):
        query = ""
        if "?" in request.path: #check if theres ? in request path
            query_list = request.path.split("?",1)
            query_string = query_list[1]
            user_parts = query_string.split('=',1) 

            if len(user_parts) == 2 and user_parts[0] == "user":
                query = user_parts[1] #extract the search query

        if not query:
            res.set_status(200, "OK")
            res.json({"users": []}) #send back empty list if query is empty
            handler.request.sendall(res.to_data())
            return
        
        users = get_user_search(query)
        res.set_status(200, "OK")
        res.json({"users": users}) #send back users list
        handler.request.sendall(res.to_data())
        return

    if method == "POST" and path == "/api/users/settings": #update current user profile
        auth_token = cookies.get("auth_token", "")
        payload = verify_jwt(auth_token) #get current username from auth token
        old_username = payload.get("username") if payload else None

        if not old_username: 
            res.set_status(401, "Unauthorized") #not logged in
            res.text("Must be logged in")
            handler.request.sendall(res.to_data())
            return

        if old_username:
            result = update_user_profile(old_username, request) #pass it on to service layer
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
            
    if method == "POST" and path == "/api/users/avatar": #update current user profile
        auth_token = cookies.get("auth_token", "")
        payload = verify_jwt(auth_token) #get current username from auth token
        username = payload.get("username") if payload else None

        if not username: 
            res.set_status(401, "Unauthorized") #not logged in
            res.text("Must be logged in")
            handler.request.sendall(res.to_data())
            return
        
        multipart_data = parse_multipart(request)
    
        file_part = None
        for part in multipart_data.parts:
            if part.name == "avatar":
                file_part = part
                break
        
        if not file_part:
            res.set_status(400, "Bad Request")
            res.text("no file provided")
            handler.request.sendall(res.to_data())
            return

        filename = file_part.headers.get("Content-Disposition", "") #get filename
        if "filename=" in filename:
            filename = filename.split('filename="')[1].split('"')[0]
            file_extension = filename.split('.')[-1].lower()
    

        if file_extension not in ["jpg", "jpeg", "png", "gif"]: #check file extensions
            res.set_status(400, "Bad Request")
            res.text("file type not supported")
            handler.request.sendall(res.to_data())
            return

        avatar_filename = str(uuid.uuid4()) + "." + file_extension #create our own filename
        avatar_path = "/public/imgs/avatars/" + avatar_filename
        avatar_url = "/public/imgs/avatars/" + avatar_filename

        with open(avatar_path, "wb") as f: #saves picture to avatar folder
            f.write(file_part.content)

        update_avatar_url_db(username, avatar_url)
        res.set_status(200, "OK")
        res.text("information updated succesfully")
        handler.request.sendall(res.to_data())

            
    if method == "POST" and path == "/api/totp/enable":
        auth_token = cookies.get("auth_token", "")
        payload = verify_jwt(auth_token)
        username = payload.get("username") if payload else None
        if not username: 
            res.set_status(401, "Unauthorized") #not logged in
            res.json({})
            handler.request.sendall(res.to_data())
            return
        
        totp_secret = enable_otp_db(username) #recieve totp secret from backend
        res.set_status(200, "OK")
        res.json({"secret": totp_secret}) #send to front end to generate qr code
        handler.request.sendall(res.to_data())

    if method == "GET" and path == "/authgithub":
        state = str(uuid.uuid4())

        client_id = os.environ.get("GITHUB_CLIENT_ID") #fetch from env file
        redirect_uri = "http://localhost:8080/authcallback" #our redirect uri

        #building the github auth url
        github_auth_url = "https://github.com/login/oauth/authorize" + "?client_id=" + client_id + "&state=" + state + "&redirect_uri=" + redirect_uri
        
        res.set_status(302, "Found")
        res.headers({"Location": github_auth_url}) #redirect it to this link
        res.state(state,600) #set state to last only 10 min
        handler.request.sendall(res.to_data())
        return
    
    if method == "GET" and path.startswith("/authcallback"):
        parameters = {}
        if "?" in path:
            query_list = request.path.split("?", 1)
            query_string = query_list[1] #get everything after the ?
            for param in query_string.split("&"): #split code and state
                key, value = param.split("=", 1) #key would equal code/state, value would be their values
                parameters[key] = value #add to dict

        returned_state = parameters.get("state")
        code = parameters.get("code")
        stored_state = cookies.get("oauth_state") #get the state sent out in authgithub

        if returned_state != stored_state: #check states if they match
            res.set_status(403, "Forbidden")
            res.text("not authorized")
            handler.request.sendall(res.to_data())
            return
        
        client_id = os.environ.get("GITHUB_CLIENT_ID") #grab clientid from env
        client_secret = os.environ.get("GITHUB_CLIENT_SECRET") #grab secret from env
        redirect_uri = "http://localhost:8080/authcallback"

        token_response = requests.post("https://github.com/login/oauth/access_token",
            json={"client_id": client_id,
                  "client_secret": client_secret,
                  "code": code,
                  "redirect_uri": redirect_uri},
                  headers={"Accept": "application/json"}) #send request to github with all 4 infos, expect an access token back
        
        if token_response.status_code != 200: #if github response is bad
            res.set_status(401, "Unauthorized")
            res.text("not authorized")
            handler.request.sendall(res.to_data())
            return

        access_token = token_response.json().get("access_token") #retrieve access token

        if not access_token: #if access token is not found, return 401
            res.set_status(401, "Unauthorized")
            res.text("no access token")
            handler.request.sendall(res.to_data())
            return

        github_response = requests.get("https://api.github.com/user", headers={"Authorization": "Bearer " + access_token})
        github_username = github_response.json().get("login") #retrieve private data, username in this case

        auth_token = oauth_login_db(github_username) #calls db to create a new user, gets back an auth token

        res.set_status(302, "Found")
        res.headers({"Location":"/"})
        res.auth_token(auth_token, 3600) #grant them the auth token in their cookies
        handler.request.sendall(res.to_data())
        return

