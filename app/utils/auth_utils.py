import os
import hmac
import hashlib
import base64
import secrets
import redis
import requests
from fastapi import Cookie, Response
from sqlalchemy.orm import Session
from dotenv import load_dotenv
from passlib.context import CryptContext
from cryptography.fernet import Fernet
from datetime import date, datetime, timezone, timedelta
from jose import jwt, JWTError, ExpiredSignatureError
from models import JwtTokens
from solapi import SolapiMessageService
from solapi.model import RequestMessage

SECRET_KEY  = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
BCRYPT = CryptContext(schemes=["bcrypt"], deprecated="auto")
FERNET = Fernet(base64.urlsafe_b64encode(hashlib.sha256(SECRET_KEY.encode()).digest()))

r = redis.Redis(host="localhost", port=6379, db=0)

# ===================================================== 일반 정규화 ===================================================== #
def normalize_phone(phone: str) -> str:
    """ 전화번호 정규화함수 """

    if not phone:
        return None

    phone = phone.replace(" ", "").replace("-", "")

    if phone.startswith("+82"):
        phone = "0" + phone[3:]

    return phone

def normalize_birth(birth_str: str) -> date:
    """ 문자열 생년월일 date 타입 변환함수 """
    formats = ["%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d"]

    for fmt in formats:
        try:
            return datetime.strptime(birth_str, fmt).date()
        except ValueError:
            continue

def convert_gender(gender: str) -> str:
    """ 성별 영문변환 함수 """
    gender = "male" if gender == "남자" else "female"
    return gender
# ===================================================== 일반 정규화 ===================================================== #

# ===================================================== 비밀번호 관련 ===================================================== #
def password_encode(password: str):
    """ 비밀번호 인코딩 -> 암호화 작업 """
    return BCRYPT.hash(password)

def password_decode(password: str, hashed_password: str):
    """ 비밀번호 디코딩 -> 암호 해독 작업 """
    return BCRYPT.verify(password, hashed_password)
# ===================================================== 비밀번호 관련 ===================================================== #

# ===================================================== 인증번호 관련 ===================================================== #
SMS_KEY = os.getenv("SMS_CLIENT_ID")
SMS_SECRET_KEY = os.getenv("SMS_CLIENT_SECRET")

# 인증번호 객체 생성
message_service = SolapiMessageService(api_key=SMS_KEY, api_secret=SMS_SECRET_KEY)

def generate_code():
    """ 인증번호 생성 함수 """
    return str(secrets.randbelow(90000) + 10000)

def send_code_to_user(phone: str, code: str):
    """ 인증번호 전송 함수 (CoolSMS 연동) """

    message = RequestMessage(
    to=phone,
    from_=os.getenv("SMS_SENDER"),
    text=f"[HANDY] 인증번호는 {code} 입니다. (3분 이내 입력)"
    )

    res = message_service.send(message)

    return res

def save_code(phone: str, code: str):
    """ 인증번호 Redis 저장 함수 - 만료시간 : 3분 """
    key = f"sms:code:{phone}"
    r.setex(key, 180, code)

def verify_code(phone: str, input_code: str):
    """ 인증번호 검증 함수 """
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
# ===================================================== 인증번호 관련 ===================================================== #

# ===================================================== 임시토큰 ===================================================== #
def encode_temp_signup_token(member_id: int):
    """ 회원가입용 임시토큰 생성 """
    exp = datetime.now(timezone.utc) + timedelta(minutes=5)

    payload = {
        "member_id": member_id,
        "type": "signup",
        "exp": exp
    }

    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token

def decode_temp_signup_token(signup_token: str | None = Cookie(None)):
    """ 회원가입용 임시토큰 해독 """

    if signup_token is None:
        return None, None
    
    try:
        payload = jwt.decode(signup_token, SECRET_KEY, algorithms=[ALGORITHM])
        member_id = payload.get("member_id")
        input_token_type = payload.get("type")

        if input_token_type != "signup":
            return None, "invalid"
        
        return member_id, None
    
    # 토큰 만료
    except ExpiredSignatureError:
        return None, "expired"

    # 유효하지 않는 토큰
    except JWTError:
        return None, "invalid"

# ===================================================== 임시토큰 ===================================================== #

# ===================================================== JWT TOKENS ===================================================== #
ACCESS_TOKEN_EXPIRE = timedelta(minutes=15)
REFRESH_TOKEN_EXPIRE = timedelta(days=7)

def create_access_token(member_id: int):
    """ JWT 액세스 토큰 생성 """
    exp = datetime.now(timezone.utc) + ACCESS_TOKEN_EXPIRE

    payload = {
        "member_id": member_id,
        "type": "access",
        "exp": exp  # 만료시간
    }

    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    return token


def create_refresh_token(member_id: int):
    """ JWT 리프레쉬 토큰 생성 """
    exp = datetime.now(timezone.utc) + REFRESH_TOKEN_EXPIRE

    payload = {
        "member_id": member_id,
        "type": "refresh",
        "exp": exp  # 만료시간
    }

    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    
    return token, exp


def verify_token(token: str, token_type: str = "access"):
    """ JWT 토큰 검증 """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        member_id = payload.get("member_id")
        input_token_type = payload.get("type")

        if not input_token_type != token_type:
            return None, "invalid"
        
        return member_id, None
    
    # 토큰 만료
    except ExpiredSignatureError:
        return None, "expired"

    # 유효하지 않는 토큰
    except JWTError:
        return None, "invalid"


def add_token_for_cookie(member_id: int, db: Session, response: Response):
    """ JWT 액세스 / 리프레시 토큰 생성 후 쿠키에 추가하는 함수 """
    access_token = create_access_token(member_id)
    refresh_token, expire = create_refresh_token(member_id)

    now = datetime.now()

    # 기존 리프레시 토큰 검증
    old_refresh_token = db.query(JwtTokens).filter(JwtTokens.member_id == member_id, JwtTokens.expires_at > now, JwtTokens.is_revoked == False).first()
    
    # 기존 리프레시 토큰 존재 시 사용불가처리
    if old_refresh_token:
        old_refresh_token.is_revoked = True
        db.commit()

    token = JwtTokens(
        member_id = member_id,
        refresh_token = refresh_token,
        expires_at = expire
    )

    db.add(token)
    db.commit()

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True
    )

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True
    )
# ===================================================== JWT TOKENS ===================================================== #