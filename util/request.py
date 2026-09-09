class Request:

    def __init__(self, request: bytes):
        # TODO: parse the bytes of the request and populate the following instance variables

        self.body = b""
        self.method = ""
        self.path = ""
        self.http_version = ""
        self.headers = {}
        self.cookies = {}

        request_parts = request.split(b'\r\n\r\n',1) #splits headers and body
        header = (request_parts[0]).decode()
        self.body = request_parts[1] if len(request_parts) > 1 else b""

        lines = header.split('\r\n')

        first_line = lines[0].split(' ') #splits the first line into method,path and http version
        self.method = first_line[0]
        self.path = first_line[1]
        self.http_version = first_line[2]

        for line in lines[1:]:
            key, value = line.split(': ') #splits all headers at the colon and add them into a dictionary
            self.headers[key] = value
            if key == "Cookie":
                cookies = value.split("; ") #specifically split cookies at semicolon
                for cookie in cookies:
                    if "=" in cookie:
                        key, value = cookie.split("=")
                        self.cookies[key] = value




def test1():
    request = Request(b'GET / HTTP/1.1\r\nHost: localhost:8080\r\nConnection: keep-alive\r\n\r\n')
    assert request.method == "GET"
    assert "Host" in request.headers
    assert request.headers["Host"] == "localhost:8080"  # note: The leading space in the header value must be removed
    assert request.body == b""  # There is no body for this request.
    # When parsing POST requests, the body must be in bytes, not str

    # This is the start of a simple way (ie. no external libraries) to test your code.
    # It's recommended that you complete this test and add others, including at least one
    # test using a POST request. Also, ensure that the types of all values are correct

def test2():
    request = Request(b'POST /api/chats HTTP/1.1\r\nHost: localhost:8080\r\nContent-Type: application/json\r\nContent-Length: 18\r\nCookie: id=123; theme=dark\r\nOrigin: http://localhost:8080\r\n\r\n{"content":"asdf"}')
    assert request.method == "POST"
    assert request.path == "/api/chats"
    assert request.http_version == "HTTP/1.1"
    assert request.headers["Content-Type"] == "application/json"
    assert request.headers["Content-Length"] == "18"
    assert request.headers["Origin"] == "http://localhost:8080"
    assert request.cookies["id"] == "123"
    assert request.cookies["theme"] == "dark"
    assert request.body == b'{"content":"asdf"}'

if __name__ == '__main__':
    test1()
    test2()
