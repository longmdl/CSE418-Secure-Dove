from util.response import Response
from service.static_service import static_service
from service.static_service import render_page_service

def static_controller(request, handler):
    mime_type = ""
    res = Response()
    path = request.path #extract the file path

    #check for correct mime type
    if ".html" in path:
        mime_type = "text/html; charset=utf-8"
    elif ".js" in path:
        mime_type = "text/javascript; charset=utf-8"
    elif ".jpg" in path:
        mime_type = "image/jpeg"
    elif ".png" in path:
        mime_type = "image/png"
    elif ".gif" in path:
        mime_type = "image/gif"
    elif ".ico" in path:
        mime_type = "image/x-icon"
    elif ".webp" in path:
        mime_type = "image/webp"
    elif ".mp4" in path:
        mime_type = "video/mp4"
    elif ".m3u8" in path:
        mime_type = "application/vnd.apple.mpegurl"
    elif ".ts" in path:
        mime_type = "video/mp2t"

    if static_service(path) == b"file not found": #if file is not found, send back 404 not found
        res.set_status(404, "Not Found")
        res.headers({"Content-Type": "text/html; charset=utf-8"})
        res.text("404 not found")
        handler.request.sendall(res.to_data())
    else: #file is found so send back proper response with file in the body
        res.set_status(200, "OK") 
        res.headers({"Content-Type": mime_type})
        res.bytes(static_service(path)) 
        handler.request.sendall(res.to_data())

def render_controller(request,handler):
    mime_type = "text/html; charset=utf-8"
    path = request.path
    res = Response()
    res.set_status(200, "OK")
    res.headers({"Content-Type": mime_type})
    res.bytes(render_page_service(path)) #returns body of static file
    handler.request.sendall(res.to_data())


        




