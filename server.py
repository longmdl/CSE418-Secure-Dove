import socketserver

from controller.chat_controller import chat_controller
from util.request import Request
from util.router import Router
from controller.static_controller import static_controller
from controller.static_controller import render_controller
from controller.auth_controller import auth_controller
from controller.websocket_controller import websocket_controller


class MyTCPHandler(socketserver.BaseRequestHandler):

    def __init__(self, request, client_address, server):
        self.router = Router()

        self.router.add_route("GET", "/public", static_controller, False)

        self.router.add_route("GET", "/", render_controller, True)
        self.router.add_route("GET", "/chat", render_controller, True)
        self.router.add_route("GET", "/register", render_controller, True)
        self.router.add_route("GET", "/login", render_controller, True)
        self.router.add_route("GET", "/settings", render_controller, True)
        self.router.add_route("GET", "/search-users", render_controller, True)

        self.router.add_route("POST", "/api/chats", chat_controller, True)
        self.router.add_route("GET", "/api/chats", chat_controller, True)
        self.router.add_route("PATCH", "/api/chats", chat_controller, False)
        self.router.add_route("DELETE", "/api/chats", chat_controller, False)

        self.router.add_route("GET", "/api/users/@me", auth_controller, True)
        self.router.add_route("GET", "/api/users/search", auth_controller, False)
        self.router.add_route("POST", "/api/users/settings", auth_controller, True)

        self.router.add_route("POST", "/api/totp/enable", auth_controller, True)

        self.router.add_route("GET", "/websocket", websocket_controller, True)

        super().__init__(request, client_address, server)

    def handle(self):
        received_data = self.request.recv(2048)
        if not received_data:
            return

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
