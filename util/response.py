import json


class Response:
    def __init__(self):
        self.status_line = "HTTP/1.1 200 OK\r\n"
        self.header_dict = { "X-Content-Type-Options": "nosniff"}
        self.cookies_dict = {}
        self.body_block = b""
        self.complete_response = b""


    def set_status(self, code, text):
        self.status_line = "HTTP/1.1 " + str(code) + " " + text + "\r\n"
        return self

    def headers(self, headers):
        self.header_dict.update(headers) #adds to the original header dict with no sniff already in it
        return self
    
    def cookies(self, cookies):
        self.cookies_dict.update(cookies) #adds to the original cookies dict everytime its called
        return self

    def bytes(self, data):
        self.body_block += data
        return self

    def text(self, data):
        data_bytes = data.encode() #encode string to bytes
        self.body_block += data_bytes
        return self
    
    def json(self, data):
        json_string = json.dumps(data) #convert from dict to json string
        json_bytes = json_string.encode() #convert from string to bytes
        self.body_block = json_bytes
        self.header_dict["Content-Type"] = "application/json"
        return self
    
    def auth_token(self, token, max_age):
        auth_token_cookie = str(token) + "; Max-Age=" + str(max_age) + "; HttpOnly; Secure" #adds an auth token with httponly and max age (and secure directive)
        self.cookies_dict["auth_token"] = auth_token_cookie
        return self
    
    def state(self, state, max_age):
        state_cookie = str(state) + "; Max-Age=" + str(max_age) + "; HttpOnly; Secure" #adds an auth token with httponly and max age (and secure directive)
        self.cookies_dict["oauth_state"] = state_cookie
        return self

    def to_data(self):
        full_response = b''
        header_line = ""
        cookie_line = ""
        content_length = len(self.body_block)
        self.header_dict["Content-Length"] = str(content_length) #calculates content length and adds to dict

        if "Content-Type" not in self.header_dict: #if no content type is set, defaults to text
            self.header_dict["Content-Type"] = "text/plain; charset=utf-8"

        for key, value in self.header_dict.items(): #goes through all the header and concatenating them
            header_line += str(key) + ": " + str(value) + "\r\n"

        for key, value in self.cookies_dict.items(): #does the same above but with cookies
            cookie_val = str(value) 
            if "Secure" not in cookie_val: #add secure to every cookie on earth
                cookie_val += "; Secure"
            cookie_line += "Set-Cookie: " +  str(key) + "=" + cookie_val + "\r\n"


        full_header = (self.status_line #building the header
                       + header_line
                       + cookie_line
                       +"\r\n")
        full_header_bytes = full_header.encode()
        full_response = full_header_bytes + self.body_block #build full response in bytes
        return full_response


def test1():
    res = Response()
    res.text("hello")
    expected = b'HTTP/1.1 200 OK\r\nContent-Type: text/plain; charset=utf-8\r\nContent-Length: 5\r\n\r\nhello'
    actual = res.to_data()


if __name__ == '__main__':
    test1()
