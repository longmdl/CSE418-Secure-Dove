from util.request import Request
from util.multipart_data import MultipartData
from util.multipart_part import MultipartPart

def parse_multipart(request):
    content_type = request.headers.get("Content-Type", "")

    boundary = content_type.split("boundary=")[1]
    boundary_full = "--" + boundary

    boundary_bytes = boundary_full.encode()

    body_parts = request.body.split(boundary_bytes)

    parts = []

    for part in body_parts[1:-1]:
        if part.startswith(b'\r\n'):
            part = part[2:] #remove the first 2 bytes \r and \n

        header_end = part.find(b'\r\n\r\n') #find index of where \r\n\r\n starts
        header_bytes = part[:header_end] #everything before \r\n\r\n

        content = part[header_end + 4:] #skip the 4 bytes \r\n\r\n and get everything after

        if content.endswith(b'\r\n'):
            content = content[:-2] #remove the last 2 bytes \r and \n

        headers = {}
        name = None

        header = header_bytes.decode()
        lines = header.split('\r\n')
        for line in lines:
            if ': ' in line:
                key, value = line.split(': ', 1)
                headers[key] = value

                if key == "Content-Disposition":
                    name = value.split('name="')[1].split('"')[0]

        parts.append(MultipartPart(headers,name,content))
        
    return MultipartData(boundary, parts)
