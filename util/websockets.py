import hashlib
import base64

from util.parsed_WS_frame import Parsed_WS_Frame

def compute_accept(ws_key):
    magic_string = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
    ws_key_concat = ws_key + magic_string
    sha1_hash = hashlib.sha1(ws_key_concat.encode('utf-8')).digest()
    accept = base64.b64encode(sha1_hash).decode('utf-8')
    return accept

def parse_ws_frame(ws_bytes):
    #byte0
    fin_bit = (ws_bytes[0] & 0b10000000) >> 7 #mask then shift
    opcode = ws_bytes[0] & 0b00001111
    
    #byte1
    mask_bit = (ws_bytes[1] & 0b10000000) >> 7
    payload_length = ws_bytes[1] & 0b01111111
    offset = 2 #move past first two bytes
    
    #payload length 
    if payload_length == 126: #next 2 bytes hold the length
        payload_length = int.from_bytes(ws_bytes[offset:offset+2], byteorder='big')
        offset += 2 #move past 2 bytes
    elif payload_length == 127: #next 8 bytes hold the length
        payload_length = int.from_bytes(ws_bytes[offset:offset+8], byteorder='big')
        offset += 8 #move past 8 bytes
        

    payload = bytearray()
    if mask_bit == 1:
        masking_key = ws_bytes[offset:offset+4] #the 4 bytes are the masking key
        offset += 4
        masked_payload = ws_bytes[offset:offset+payload_length]
        
        for i in range(payload_length):
            unmasked_byte = masked_payload[i] ^ masking_key[i % 4] #xor the payload bytes with the right mask byte
            payload.append(unmasked_byte)
    else:
        payload = ws_bytes[offset:offset+payload_length]

    parsed_WS_Frame = Parsed_WS_Frame(fin_bit, opcode, payload_length, bytes(payload))
        
    return parsed_WS_Frame

def generate_ws_frame(payload_bytes):
    payload_length = len(payload_bytes)
    
    
    frame = bytearray([0b10000001])  #set fin bit=1, opcode=1
    
    #no mask bit (0), set payload length
    if payload_length < 126:
        frame.append(payload_length)
    elif payload_length <= 65535:
        frame.append(126)
        frame.extend(payload_length.to_bytes(2, byteorder='big'))
    else:
        frame.append(127)
        frame.extend(payload_length.to_bytes(8, byteorder='big'))
    
    frame.extend(payload_bytes) #append the payload
    return bytes(frame)