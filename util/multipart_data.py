class MultipartData:
    def __init__(self, boundary, parts):
        self.boundary = boundary
        self.parts = parts