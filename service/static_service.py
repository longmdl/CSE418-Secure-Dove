def static_service(path):
    if path.startswith("/"):
        path = path[1:]
    data = b""
    try:
        with open(path, 'rb') as f:
            data = f.read() #read file from the given path as bytes
    except FileNotFoundError:
        data = b"file not found" #send back a file not found in bytes
    return data

def render_page_service(path):
    layout = read_file("public/layout/layout.html")
    
    if path == "/chat":
        content = read_file("public/chat.html")
        rendered = layout.replace("{{content}}", content) #replacing it with chat content
        rendered_bytes = rendered.encode()
        return rendered_bytes
    elif path == "/":
        content = read_file("public/index.html")
        rendered = layout.replace("{{content}}", content) #replacing it with front page
        rendered_bytes = rendered.encode()
        return rendered_bytes
    elif path == "/register":
        content = read_file("public/register.html")
        rendered = layout.replace("{{content}}", content) #replacing it with register page
        rendered_bytes = rendered.encode()
        return rendered_bytes
    elif path == "/login":
        content = read_file("public/login.html")
        rendered = layout.replace("{{content}}", content) #replacing it with login page
        rendered_bytes = rendered.encode()
        return rendered_bytes
    elif path == "/settings":
        content = read_file("public/settings.html")
        rendered = layout.replace("{{content}}", content) #replacing it with settings page
        rendered_bytes = rendered.encode()
        return rendered_bytes
    elif path == "/search-users":
        content = read_file("public/search-users.html")
        rendered = layout.replace("{{content}}", content) #replacing it with search users page
        rendered_bytes = rendered.encode()
        return rendered_bytes
    elif path == "/change-avatar":
        content = read_file("public/change-avatar.html")
        rendered = layout.replace("{{content}}", content) #replacing it with change avatar page
        rendered_bytes = rendered.encode()
        return rendered_bytes
    elif path == "/videotube":
        content = read_file("public/videotube.html")
        rendered = layout.replace("{{content}}", content)
        return rendered.encode()
    elif path == "/videotube/upload":
        content = read_file("public/upload.html")
        rendered = layout.replace("{{content}}", content)
        return rendered.encode()
    elif path.startswith("/videotube/videos/"):
        content = read_file("public/view-video.html")
        rendered = layout.replace("{{content}}", content)
        return rendered.encode()
    elif path.startswith("/videotube/set-thumbnail"):
        content = read_file("public/set-thumbnail.html")
        rendered = layout.replace("{{content}}", content)
        return rendered.encode()
    elif path == "/test-websocket":
        content = read_file("public/test-websocket.html")
        rendered = layout.replace("{{content}}", content)
        rendered_bytes = rendered.encode()
        return rendered_bytes
    elif path == "/drawing-board":
        content = read_file("public/drawing-board.html")
        rendered = layout.replace("{{content}}", content)
        rendered_bytes = rendered.encode()
        return rendered_bytes
    elif path == "/video-call":
        content = read_file("public/video-call.html")
        rendered = layout.replace("{{content}}", content)
        return rendered.encode()
    elif path.startswith("/video-call/"):
        content = read_file("public/video-call-room.html")
        rendered = layout.replace("{{content}}", content)
        return rendered.encode()

def read_file(path):
    try:
        with open(path, 'r') as f:
            data = f.read() #read file from the given path as text
            return data
    except FileNotFoundError:
        data = f"" #send back an empty file
        return data