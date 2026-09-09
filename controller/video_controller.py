import json
import os
import uuid
from util.response import Response
from util.multipart import parse_multipart
from service.video_service import upload_video, get_all_videos, get_video, update_video_thumbnail
from util.auth import verify_jwt
import service.websocket_service as ws_service

def video_controller(request, handler):
    res = Response()
    path = request.path
    method = request.method
    
    cookies = request.cookies
    token = cookies.get("auth_token")
    payload = verify_jwt(token) #auth logic
    author_name = payload.get("username") if payload else None
    
    if not author_name: #not logged in
        res.set_status(401, "Unauthorized")
        res.text("Unauthorized")
        handler.request.sendall(res.to_data())
        return
    
    if method == "POST" and path == "/api/video-calls": #handle video calls
        body_dict = json.loads(request.body.decode())
        room_name = body_dict.get("name", "Unnamed Room")
        
        room_id = str(uuid.uuid4())
        
        ws_service.create_room(room_id, room_name)

        res.set_status(200, "OK")
        res.json({"id": room_id})
        handler.request.sendall(res.to_data())
        return
    
    if method == "POST" and path == "/api/videos": #post a video
        multipart_data = parse_multipart(request)
        title = ""
        description = ""
        video_part = None
        
        for part in multipart_data.parts: #retrieve info from parts
            if part.name == "title":
                title = part.content.decode()
            elif part.name == "description":
                description = part.content.decode()
            elif part.name == "video":
                video_part = part
        
        if video_part:
            video_filename = str(uuid.uuid4()) + ".mp4"
            video_path = "public/videos/" + video_filename

            os.makedirs("public/videos/", exist_ok=True)
            
            with open(video_path, "wb") as f:
                f.write(video_part.content) #saves to file locally
                
            video_id = upload_video(title, description, video_filename, author_name) #service layer will return a video id, sent back in response
            
            res.set_status(200, "OK")
            res.headers({"Content-Type": "application/json"})
            res.text(json.dumps({"id": video_id})) 
        else:
            res.set_status(400, "Bad Request")
            res.text("video upload failed")
            
        handler.request.sendall(res.to_data())
        return
    
    elif method == "GET" and path == "/api/videos": #get all videos
        videos_data = get_all_videos()
        res.set_status(200, "OK")
        res.headers({"Content-Type": "application/json"})
        res.text(json.dumps(videos_data))
        handler.request.sendall(res.to_data())
        return

    elif method == "GET" and path.startswith("/api/videos/"): #get specific video
        video_id = path.split("/")[-1]
        video_data = get_video(video_id)
        
        if video_data:
            res.set_status(200, "OK")
            res.headers({"Content-Type": "application/json"})
            res.text(json.dumps(video_data))
        else:
            res.set_status(404, "Not Found")
            res.text("Video not found")
            
        handler.request.sendall(res.to_data())
        return
    elif method == "PUT" and path.startswith("/api/thumbnails/"):
        video_id = path.split("/")[-1]
        
        body_dict = json.loads(request.body.decode())
        new_thumbnail_url = body_dict.get("thumbnailURL")
        
        if new_thumbnail_url:
            success = update_video_thumbnail(video_id, new_thumbnail_url, author_name)
            
            if success:
                res.set_status(200, "OK")
                res.headers({"Content-Type": "application/json"})
                res.text(json.dumps({"message": "successfully updated thumbnail"}))
            else:
                res.set_status(403, "Forbidden")
                res.text(json.dumps({"message": "Video not found or user not allowed"}))
        else:
            res.set_status(400, "Bad Request")
            res.text(json.dumps({"message": "Missing thumbnailURL"}))

        handler.request.sendall(res.to_data())

    else:
        res.set_status(404, "Not Found")
        res.headers({"Content-Type": "text/html; charset=utf-8"})
        res.text("Something went wrong")
        handler.request.sendall(res.to_data()) 
        return
    