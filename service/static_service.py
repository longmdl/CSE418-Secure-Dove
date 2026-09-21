PAGES = {
    "/": "public/index.html",
    "/chat": "public/chat.html",
    "/register": "public/register.html",
    "/login": "public/login.html",
    "/settings": "public/settings.html",
    "/search-users": "public/search-users.html",
}


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
    page = PAGES.get(path)
    if not page: #nothing to render for an unknown page
        return b"404 not found"

    layout = read_file("public/layout/layout.html")
    content = read_file(page)
    rendered = layout.replace("{{content}}", content) #drop the page into the shared layout
    return rendered.encode()

def read_file(path):
    try:
        with open(path, 'r') as f:
            data = f.read() #read file from the given path as text
            return data
    except FileNotFoundError:
        data = "" #send back an empty file
        return data
