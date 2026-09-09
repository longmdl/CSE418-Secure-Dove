from dotenv import load_dotenv
load_dotenv()

import socketserver

from controller.chat_controller import chat_controller
from util.request import Request
from util.router import Router
from util.hello_path import hello_path
from controller.static_controller import static_controller
from controller.static_controller import render_controller  
from controller.auth_controller import auth_controller
from controller.video_controller import video_controller
from controller.websocket_controller import websocket_controller


class MyTCPHandler(socketserver.BaseRequestHandler):

    def __init__(self, request, client_address, server):
        self.router = Router()
        self.router.add_route("GET", "/hello", hello_path, True)
        # TODO: Add your routes here
        self.router.add_route("GET", "/public", static_controller, False)
        self.router.add_route("GET", "/", render_controller, True)
        self.router.add_route("GET", "/chat", render_controller, True)
        self.router.add_route("GET", "/register", render_controller, True)
        self.router.add_route("GET", "/login", render_controller, True)
        self.router.add_route("GET", "/settings", render_controller, True)
        self.router.add_route("GET", "/search-users", render_controller, True)

        self.router.add_route("POST", "/api/chats",chat_controller, True)
        self.router.add_route("GET", "/api/chats", chat_controller, True)
        self.router.add_route("PATCH", "/api/chats", chat_controller, False)
        self.router.add_route("DELETE", "/api/chats", chat_controller, False)

        self.router.add_route("PATCH", "/api/reaction", chat_controller, False)
        self.router.add_route("DELETE", "/api/reaction", chat_controller, False)

        self.router.add_route("PATCH", "/api/nickname", chat_controller, True)

        #self.router.add_route("POST", "/register", auth_controller, True)
        #self.router.add_route("POST", "/login", auth_controller, True)
        #self.router.add_route("GET", "/logout", auth_controller, True)
        self.router.add_route("GET", "/api/users/@me", auth_controller, True)   
        self.router.add_route("GET", "/api/users/search", auth_controller, False)
        self.router.add_route("POST", "/api/users/settings", auth_controller, True)

        self.router.add_route("POST", "/api/totp/enable", auth_controller, True)

        self.router.add_route("GET", "/authgithub", auth_controller, True)
        self.router.add_route("GET", "/authcallback", auth_controller, False)

        self.router.add_route("GET", "/change-avatar", render_controller, True)
        self.router.add_route("POST", "/api/users/avatar", auth_controller, True)

        self.router.add_route("GET", "/videotube", render_controller, True)
        self.router.add_route("GET", "/videotube/upload", render_controller, True)
        self.router.add_route("GET", "/videotube/videos/", render_controller, False)

        self.router.add_route("POST", "/api/videos", video_controller, True)
        self.router.add_route("GET", "/api/videos", video_controller, True)
        self.router.add_route("GET", "/api/videos/", video_controller, False)

        self.router.add_route("GET", "/videotube/set-thumbnail", render_controller, False)
        self.router.add_route("PUT", "/api/thumbnails/", video_controller, False)

        self.router.add_route("GET", "/test-websocket", render_controller, True)
        self.router.add_route("GET", "/drawing-board", render_controller, True)
        self.router.add_route("GET", "/video-call", render_controller, True)
        self.router.add_route("GET", "/video-call/", render_controller, False)
        self.router.add_route("GET", "/websocket", websocket_controller, True)

        self.router.add_route("POST", "/api/video-calls", video_controller, True)
        
        super().__init__(request, client_address, server)

    def handle(self):
        received_data = self.request.recv(2048)
        if not received_data:
            return
        
        print(self.client_address)
        print("--- received data ---")
        print("trust me theres something here")
        print("--- end of data ---\n\n")
        request = Request(received_data)

        content_length_str = request.headers.get("Content-Length", "0") #extract content length
        content_length = int(content_length_str) 
        body_part = request.body 
        remaining_bytes = content_length - len(body_part) #amount recieve so far

        while remaining_bytes > 0:
            new_part = self.request.recv(2048)
            body_part += new_part
            remaining_bytes -= len(new_part)

        request.body = body_part

        self.router.route_request(request, self)


def main():
    host = "0.0.0.0"
    port = 8080
    socketserver.ThreadingTCPServer.allow_reuse_address = True

    server = socketserver.ThreadingTCPServer((host, port), MyTCPHandler)

    print("Listening on port " + str(port))
    server.serve_forever()


if __name__ == "__main__":
    main()
