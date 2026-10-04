import json
from util.response import Response
import service.websocket_service as ws_service
from util.websockets import compute_accept, parse_ws_frame
from util.auth import verify_jwt


def websocket_controller(request, handler):
    res = Response()
    if request.headers.get("Upgrade", "").lower() != "websocket":
        res.set_status(400, "Bad Request")
        res.text("Bad Request")
        handler.request.sendall(res.to_data())
        return
    
    auth_token = request.cookies.get("auth_token", "")
    payload = verify_jwt(auth_token)
    user_id = payload.get("sub") if payload else None
    username = payload.get("username") if payload else None

    if not user_id or not username:
        res.set_status(401, "Unauthorized")
        res.text("Unauthorized")
        handler.request.sendall(res.to_data())
        return

    ws_key = request.headers.get("Sec-WebSocket-Key", "")

    if not ws_key:
        res = Response()
        res.set_status(400, "Bad Request")
        res.text("Bad Request")
        handler.request.sendall(res.to_data())
        return

    perform_handshake(handler, ws_key)
    ws_service.register(handler, user_id, username)
    run_receive_loop(handler)
    ws_service.unregister(handler)


def perform_handshake(handler, ws_key):
    accept_key = compute_accept(ws_key)
    response = (
        "HTTP/1.1 101 Switching Protocols\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        "Sec-WebSocket-Accept: " + accept_key + "\r\n"
        "\r\n")
    handler.request.sendall(response.encode())


def run_receive_loop(handler):
    buffer = b""

    multi_frame_message = bytearray() #handle fragmented ws frames

    while True:
        try:
            data = handler.request.recv(2048)
        except Exception:
            break

        if not data:
            break

        buffer += data

        while True:
            if len(buffer) < 2:
                break

            payload_length = buffer[1] & 0b01111111
            header_offset = 2

            if payload_length == 126:
                if len(buffer) < 4:
                    break
                payload_length = int.from_bytes(buffer[2:4], byteorder='big')
                header_offset = 4
            elif payload_length == 127:
                if len(buffer) < 10:
                    break
                payload_length = int.from_bytes(buffer[2:10], byteorder='big')
                header_offset = 10

            if (buffer[1] & 0b10000000) >> 7:  #mask bit set, skip 4 byte masking key
                header_offset += 4

            total_frame_length = header_offset + payload_length

            if len(buffer) < total_frame_length:
                break

            frame_bytes = buffer[:total_frame_length]
            buffer = buffer[total_frame_length:]

            parsed = parse_ws_frame(frame_bytes)

            if parsed.opcode == 8:  #close frame
                return

            if parsed.opcode == 1 or parsed.opcode == 0: #if opcode 1 (first text frame that is maybeee fragmented?!) or opocde 0 (middle and last frame)
                multi_frame_message.extend(parsed.payload)
                
                if parsed.fin_bit == 1: #final fragment from fragmented frame
                    dispatch_text_frame(handler, multi_frame_message.decode())
                    multi_frame_message.clear()


def dispatch_text_frame(handler, payload_str):
    if not payload_str.strip().startswith("{"):
        return
    message_data = json.loads(payload_str)
    ws_service.handle_message(handler, message_data)