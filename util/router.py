from util.response import Response

class Router:

    def __init__(self):
        self.all_routes = []


    def add_route(self, method, path, action, exact_path=False):
        self.all_routes.append({"method": method,"path": path,"action": action,"exact_path": exact_path})
        pass

    def route_request(self, request, handler):
        try: #implement top level error handler to wrap every route 
            for route in self.all_routes:
                if request.method == route["method"] and request.path == route["path"] and route["exact_path"] == True:
                    action =  route["action"]
                    action(request, handler)
                    return
                elif request.method == route["method"] and request.path.startswith(route["path"]) and route["exact_path"] == False:
                    action = route["action"]
                    action(request, handler)
                    return
        except Exception as e:
            print("Unexpected error:", e)
            response = Response()
            response.set_status(500, "Unexpected Error")
            response.json({"error": "Unexpected Error"})
            handler.request.sendall(response.to_data())
            return 
            

        response = Response()
        response.set_status(404, "Not Found")
        response.headers({"Content-Type": "text/html; charset=utf-8"})
        response.text("404 not found lol")
        handler.request.sendall(response.to_data())

