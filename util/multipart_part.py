class MultipartPart:
    def __init__(self, headers, name, content):
        self.headers = headers
        self.name = name
        self.content = content