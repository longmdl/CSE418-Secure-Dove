from util.request import Request
import jwt


def verify_jwt(token):
    if not token:
        return None
    try:
        with open("/root/keys/jwt_public.pem", "rb") as f:
            PUBLIC_KEY = f.read()
        payload = jwt.decode(token, PUBLIC_KEY, algorithms=["RS256"])
        return payload
    except jwt.ExpiredSignatureError:
        print("Token has expired")
        return None
    except jwt.InvalidTokenError:
        print("Invalid Token")
        return None

def extract_credentials(request):
    body = request.body
    body_string = body.decode()
    body_parts = body_string.split('&',1) #split username and password (and otp) with &
    username = body_parts[0].split('=',1)[1] #split it again with =
    
    password_otp_parts = body_parts[1]
    totp_code = None
    if '&' in password_otp_parts: #handle edge cases where password have & in it
        split_index = password_otp_parts.rfind('&') #find the last & to get totp
        password_part = password_otp_parts[:split_index] #the part before the last & is allll password
        totp_part = password_otp_parts[split_index+1:] #after the last & is totp
        if totp_part.startswith('totp'):
            totp_code = totp_part.split('=', 1)[1] #extract the totp code
    else:
        password_part = password_otp_parts #if theres only 2 parts, this is the password part

    encoded_password = password_part.split('=', 1)[1] #extract the url encoded password

    result = []

    url_encoded_char_dict = {
    '%21': '!',
    '%40': '@',
    '%23': '#',
    '%24': '$',
    '%5E': '^',
    '%5e': '^',
    '%28': '(',
    '%29': ')',
    '%2D': '-',
    '%2d': '-',
    '%5F': '_',
    '%5f': '_',
    '%3D': '=',
    '%3d': '=',
    '%26': '&',
    '%25': '%'
    } #dict of the special characters we have to handle

    decoded_password = encoded_password
    for k,v in url_encoded_char_dict.items():
        decoded_password = decoded_password.replace(k, v) #replace all the url encoded string with their actual char

    result.append(username)
    result.append(decoded_password)
    if totp_code:
        result.append(totp_code)
    return result

def validate_password(password):
    if len(password) < 8:
        return False
    if not any(char.islower() for char in password):
        return False
    if not any(char.isupper() for char in password):
        return False
    if not any(char.isnumeric() for char in password):
        return False
    
    special_char_list = ['!', '@', '#', '$', '%', '^', '&', '(', ')', '-', '_', '='] 
    if not any(char in special_char_list for char in password): #if it doesnt contain a special char, return false
        return False
    
    for char in password:
        if not char.isalnum():
            if not char in special_char_list: #if it includes special char outside of the on we handle, return false 
                return False
            
    return True


