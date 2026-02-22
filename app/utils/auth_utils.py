import os
import hmac
import hashlib
import base64
import secrets
import redis
import requests
from dotenv import load_dotenv
from passlib.context import CryptContext
from cryptography.fernet import Fernet
from datetime import datetime, timezone

SECRET_KEY  = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
SMS_KEY = os.getenv("SMS_CLIENT_ID")
SMS_SECRET_KEY = os.getenv("SMS_CLIENT_SECRET")

BCRYPT = CryptContext(schemes=["bcrypt"], deprecated="auto")
FERNET = Fernet(base64.urlsafe_b64encode(hashlib.sha256(SECRET_KEY.encode()).digest()))

r = redis.Redis(host="localhost", port=6379, db=0)

def generate_signature(api_secret: str, date_time: str, salt: str) -> str:
    """ SMS 문자전송 객체 생성함수 """
    data = date_time + salt
    signature = hmac.new(
        api_secret.encode(),
        data.encode(),
        hashlib.sha256
    ).hexdigest()
    return signature

def create_auth_header(api_key: str, api_secret: str) -> str:
    """ Authorization 헤더 생성 """
    date_time = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    salt = secrets.token_hex(16)
    signature = generate_signature(api_secret, date_time, salt)
    
    return f"HMAC-SHA256 apiKey={api_key}, date={date_time}, salt={salt}, signature={signature}"

def normalize_phone(phone: str) -> str:
    """ 전화번호 정규화함수 """

    if not phone:
        return None

    phone = phone.replace(" ", "").replace("-", "")

    if phone.startswith("+82"):
        phone = "0" + phone[3:]

    return phone

def password_encode(password: str):
    """ 비밀번호 인코딩 -> 암호화 작업 """
    return BCRYPT.hash(password)

def password_decode(password: str, hashed_password: str):
    """ 비밀번호 디코딩 -> 암호 해독 작업 """
    return BCRYPT.verify(password, hashed_password)

def generate_code():
    """ 인증번호 생성 함수 """
    return str(secrets.randbelow(90000) + 10000)

def send_code_to_user(phone: str, code: str):
    """ 인증번호 전송 함수 (CoolSMS 연동) """

    auth_header = create_auth_header(SMS_KEY, SMS_SECRET_KEY)

    headers = {
        "Authorization": auth_header,
        "Content-Type": "application/json"
    }

    message_data = {
        "messages": [
            {
                "to": phone,
                "from": os.getenv("SMS_SENDER"),
                "text": f"[HANDY] 인증번호는 {code} 입니다. (3분 이내 입력)"
            }
        ]
    }

    response = requests.post(
        "https://api.solapi.com/messages/v4/send-many/detail",
        json=message_data,
        headers=headers,
        timeout=5
    )

    response.raise_for_status()
    return response.json()

def save_code(phone: str, code: str):
    """ 인증번호 Redis 저장 함수 - 만료시간 : 3분 """
    key = f"sms:code:{phone}"
    r.setex(key, 180, code)

def verify_code(phone: str, input_code: str):
    key = f"sms:code:{phone}"
    stored_code = r.get(key)

    if not stored_code:
        return False, "인증번호가 만료되었어요"

    if stored_code.decode() != input_code:
        return False, "올바르지 않은 인증번호에요. 인증번호를 확인해주세요"

    r.delete(key)

    r.setex(f"sms:verified:{phone}", 600, "true")

    return True, "인증 되었습니다."

def check_daily_limit(phone: str):
    """ 인증번호 재전송 함수 - 하루 5회 제한 """
    key = f"sms:count:{phone}"
    cnt = r.get(key)

    if cnt and int(cnt) >= 5:
        return False
    
    pipe = r.pipeline()
    pipe.incr(key)
    pipe.ttl(key)
    count, ttl = pipe.execute()

    if ttl == -1:
        r.expire(key, 86400)

    return True