import os
import httpx
import uuid
import logging
import jwt
import time
import json
from jwt.algorithms import RSAAlgorithm
from fastapi import APIRouter, Depends, Query, Cookie, HTTPException, Response, Form
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from sqlalchemy import text, func
from sqlalchemy.orm import Session
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timedelta

from models import Member, SocialAccount, JwtTokens
from database import get_db, SessionLocal
from utils.auth_utils import normalize_phone, normalize_birth, convert_gender, password_encode, password_decode, generate_code, save_code, send_code_to_user, verify_code, check_daily_limit, add_token_for_cookie, encode_temp_signup_token, decode_temp_signup_token, verify_token
from schemas.login import ValidLogin, Signup, PhoneReq, VerifyReq, AppleCallbackRequest

logger = logging.getLogger(__name__)

ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(ENV_PATH)

KAKAO_CLIENT_ID = os.getenv("KAKAO_CLIENT_ID")
KAKAO_CLIENT_SECRET = os.getenv("KAKAO_CLIENT_SECRET")
KAKAO_REDIRECT_URI = os.getenv("KAKAO_REDIRECT_URI")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

APPLE_CLIENT_ID = os.getenv("APPLE_CLIENT_ID")
APPLE_TEAM_ID = os.getenv("APPLE_TEAM_ID")
APPLE_KEY_ID = os.getenv("APPLE_KEY_ID")
APPLE_PRIVATE_KEY = os.getenv("APPLE_PRIVATE_KEY")
APPLE_REDIRECT_URI = os.getenv("APPLE_REDIRECT_URI")

FRONTEND_URL = os.getenv("VITE_API_URL")

router = APIRouter(prefix="/api/auth", tags=["소셜 로그인 관리"])

_state_store = {}

# ===================================================== JWT 토큰 검증 ===================================================== #
@router.post("/me")
def verify_tokens(access_token: str = Cookie(None)):
    """
    ----------------------------------------
    JWT 토큰 검증 API
    ----------------------------------------
    """
    return verify_token(access_token, "access")
# ===================================================== JWT 토큰 검증 ===================================================== #

# ===================================================== 일반 로그인 ===================================================== #
@router.post("/login")
def general_login(req: ValidLogin, response: Response, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    로그인 API
    ----------------------------------------
    """

    user = db.query(Member).filter(Member.phone == req.phone).first()

    if not user:
        raise HTTPException(status_code=401, detail="아직 가입된 계정이 없어요. 회원가입을 진행해 주세요.")
    else:
        if not password_decode(req.password, user.password):
            raise HTTPException(status_code=401, detail="전화번호 또는 비밀번호가 올바르지 않아요.")
        
    add_token_for_cookie(user.id, db, response)

    return {"success": True}
# ===================================================== 일반 로그인 ===================================================== #
      
# ===================================================== 인증번호 ===================================================== #
@router.post("/signup/code/send")
def send_sms(req: PhoneReq, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    회원가입용 인증코드 발송 API
    ----------------------------------------
    """
    phone = normalize_phone(req.phone)

    member = db.query(Member).filter(Member.phone == phone).first()

    if member:
        raise HTTPException(status_code=400, detail="이미 가입된 회원이에요")

    if not check_daily_limit(phone):
        raise HTTPException(status_code=400, detail="인증번호는 하루 최대 5번까지 발송 가능해요")

    code = generate_code()
    print(code)
    # send_code_to_user(phone, code)
    save_code(phone, code)

    return {"message": "인증번호 발송 완료"}

@router.post("/signup/code/verify")
def verify_sms(req: VerifyReq):
    """
    ----------------------------------------
    회원가입용 인증코드 검증 API
    ----------------------------------------
    """
    phone = normalize_phone(req.phone)
    code = req.code

    valid, msg = verify_code(phone, code)

    if not valid:
        raise HTTPException(400, msg)
    
    return {"message": msg}
# ===================================================== 인증번호 ===================================================== #

# ===================================================== 회원가입 ===================================================== #
@router.post("/signup")
def signup(req: Signup, res: Response, db: Session = Depends(get_db), signup_token: dict = Depends(decode_temp_signup_token)):
    """
    ----------------------------------------
    회원가입 API
    ----------------------------------------
    """
    member_id, error = signup_token
    existing = db.query(Member).filter(Member.phone == req.phone).first()

    if existing:
        raise HTTPException(status_code=400, detail="이미 가입된 번호입니다.")
    
    phone = normalize_phone(req.phone)
    hashed_pw = password_encode(req.password)
    birth = normalize_birth(req.birth)
    gender = convert_gender(req.gender)
    image_url = str(uuid.uuid4()) + req.imageUrl if req.imageUrl else "default.png"

    if req.type == "social":
        member = db.query(Member).filter(Member.id == member_id).first()
        member.phone = phone
        member.name = req.name
        member.birth = birth
        member.gender = gender
        member.image_url = image_url

    else:
        member = Member(
            phone = phone,
            password = hashed_pw,
            name = req.name,
            birth = birth,
            gender = gender,
            image_url = image_url,
        )
        db.add(member)
        
    db.commit()

    # 회원가입용 임시토큰 삭제
    res.delete_cookie(key="signup_token")
# ===================================================== 회원가입 ===================================================== #

# ===================================================== 로그아웃 ===================================================== #
@router.post("/logout")
def logout(res: Response, access_token: str = Cookie(None), refresh_token: str = Cookie(None), db: Session = Depends(get_db)):
    """
    ----------------------------------------
    로그아웃 API
    ----------------------------------------
    """

    if refresh_token:
        token = db.query(JwtTokens).filter(JwtTokens.refresh_token == refresh_token, JwtTokens.is_revoked == False).first()

        if token:
            token.is_revoked = True
            db.commit()

    res.delete_cookie(key="refresh_token")
    res.delete_cookie(key="access_token")

    return JSONResponse(status_code=200, content={"message": "로그아웃 완료"})
# ===================================================== 로그아웃 ===================================================== #

# ===================================================== 카카오 로그인 ===================================================== #
@router.get("/kakao/login")
def kakao_login():
    """
    ----------------------------------------
    카카오 소셜로그인 API
    ----------------------------------------
    """
    state = str(uuid.uuid4())
    _state_store[state] = datetime.now() + timedelta(minutes=10)
    
    login_url = (
        "https://kauth.kakao.com/oauth/authorize"
        f"?response_type=code&client_id={KAKAO_CLIENT_ID}"
        f"&redirect_uri={KAKAO_REDIRECT_URI}&state={state}&prompt=login"
    )

    return RedirectResponse(url=login_url)


@router.get("/kakao/callback")
async def kakao_callback(code: str, state: str, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    카카오 소셜로그인 콜백 API
    ----------------------------------------
    """
    # state 검증
    if state not in _state_store or _state_store[state] < datetime.now():
        _state_store.pop(state, None)
        return JSONResponse(status_code=400, content={"error": "유효하지 않은 요청입니다."})
    
    del _state_store[state]
    
    # 토큰 교환
    token_url = "https://kauth.kakao.com/oauth/token"
    token_data = {
        "grant_type": "authorization_code",
        "client_id": KAKAO_CLIENT_ID,
        "redirect_uri": KAKAO_REDIRECT_URI,
        "client_secret": KAKAO_CLIENT_SECRET,
        "code": code,
    }

    try:
        async with httpx.AsyncClient() as client:
            token_res = await client.post(token_url, data=token_data, timeout=10)
        
        if token_res.status_code != 200:
            logger.error(f"Token exchange failed: {token_res.text}")
            return JSONResponse(status_code=400, content={"error": "토큰 발급 실패"})
        
        token_json = token_res.json()
        access_token = token_json.get("access_token")
        if not access_token:
            return JSONResponse(status_code=400, content={"error": "토큰 없음"})
        
    except Exception as e:
        logger.error(f"Token request failed: {str(e)}")
        return JSONResponse(status_code=502, content={"error": "카카오 서버 오류"})
    
    # 사용자 정보 조회
    try:
        async with httpx.AsyncClient() as client:
            user_res = await client.get(
                "https://kapi.kakao.com/v2/user/me",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10
            )
        
        if user_res.status_code != 200:
            logger.error(f"User info failed: {user_res.text}")
            return JSONResponse(status_code=400, content={"error": "사용자 정보 조회 실패"})
        
        user_json = user_res.json()
        
    except Exception as e:
        logger.error(f"User info request failed: {str(e)}")
        return JSONResponse(status_code=502, content={"error": "카카오 서버 오류"})

    kakao_id = user_json.get("id")
    if not kakao_id:
        logger.error(f"No kakao id: {user_json}")
        return JSONResponse(status_code=400, content={"error": "사용자 ID 없음"})
    
    provider_id = user_json.get("id")

    kakao_account = user_json.get("kakao_account", {}) or {}
    name = kakao_account.get("name")
    phone = normalize_phone(kakao_account.get("phone_number"))
    birthday = datetime.strptime(kakao_account.get("birthyear") + kakao_account.get("birthday"), "%Y%m%d").date()
    gender = kakao_account.get("gender")
    
    expires_in = int(token_json.get("expires_in", 6 * 60 * 60))

    try:
        # 기존 회원 조회
        social_account = db.query(SocialAccount).filter(SocialAccount.provider == 'kakao').filter(SocialAccount.provider_id == str(provider_id)).first()

        # 신규 회원일 경우
        if not social_account:
            member = Member(
                phone = None,
                name = None,
                birth = None,
                gender = None,
            )
            db.add(member)
            db.flush()

            social = SocialAccount(
                member_id = member.id,
                provider = 'kakao',
                provider_id = provider_id
            )

            db.add(social)
            db.commit()
            db.flush()

            temp_token = encode_temp_signup_token(member.id)

            res = RedirectResponse(url=f"{FRONTEND_URL}/#/signup?type=social")
            res.set_cookie(
                key="signup_token",
                value=temp_token,
                httponly=True,
                max_age=300
            )

        # 기존회원일 경우
        else:
            member = db.query(Member).filter(Member.id == social_account.member_id).first()

            if member.phone is None and member.name is None:
                temp_token = encode_temp_signup_token(member.id)
                res = RedirectResponse(url=f"{FRONTEND_URL}/#/signup?type=social")
                res.set_cookie(key="signup_token", value=temp_token, httponly=True, max_age=300)
                return res

            res = RedirectResponse(url=f"{FRONTEND_URL}/#/onboarding/member-type")
            add_token_for_cookie(social_account.member_id, db, res)
            return res

    except Exception as e:
        db.rollback()
        logger.exception("DB error")
        return JSONResponse(status_code=500, content={"error": "DB 오류"})
    
# ===================================================== 카카오 로그인 ===================================================== #

# ===================================================== 구글 로그인 ===================================================== #
@router.get("/google/login")
def google_login():
    """
    ----------------------------------------
    구글 소셜로그인 API
    ----------------------------------------
    """
    state = str(uuid.uuid4())
    _state_store[state] = datetime.now() + timedelta(minutes=10)

    google_auth_url = (
        f"https://accounts.google.com/o/oauth2/auth"
        f"?response_type=code"
        f"&client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={GOOGLE_REDIRECT_URI}"
        f"&scope=openid%20email%20profile"
        f"&prompt=select_account"
        f"&state={state}"
    )

    return RedirectResponse(url=google_auth_url)


@router.get("/google/callback")
async def google_callback(code: str, state: str, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    구글 소셜로그인 콜백 API
    ----------------------------------------
    """
    # state 검증
    if state not in _state_store or _state_store[state] < datetime.now():
        _state_store.pop(state, None)
        return JSONResponse(status_code=400, content={"error": "유효하지 않은 요청입니다."})
    
    del _state_store[state]

    # 토큰 교환
    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "grant_type": "authorization_code",
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "code": code,
        "state": state
    }

    try:
        async with httpx.AsyncClient() as client:
            token_res = await client.post(token_url, data=token_data, timeout=10)

        if token_res.status_code != 200:
            logger.error(f"Token exchange failed: {token_res.text}")
            return JSONResponse(status_code=400, content={"error": "토큰 발급 실패"})
        
        token_json = token_res.json()
        access_token = token_json.get("access_token")
        if not access_token:
            return JSONResponse(status_code=400, content={"error": "토큰 없음"})
        
    except Exception as e:
        logger.error(f"Token request failed: {str(e)}")
        return JSONResponse(status_code=502, content={"error": "구글 서버 오류"})
    
    # 사용자 정보 조회
    try:
        async with httpx.AsyncClient() as client:
            user_res = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10
            )
        
        if user_res.status_code != 200:
            logger.error(f"User info failed: {user_res.text}")
            return JSONResponse(status_code=400, content={"error": "사용자 정보 조회 실패"})
        
        user_json = user_res.json()
        
    except Exception as e:
        logger.error(f"User info request failed: {str(e)}")
        return JSONResponse(status_code=502, content={"error": "구글 서버 오류"})
    
    provider_id = user_json.get("sub")

    expires_in = int(token_json.get("expires_in", 6 * 60 * 60))

    try:
        social_account = db.query(SocialAccount).filter(SocialAccount.provider == 'google').filter(SocialAccount.provider_id == str(provider_id)).first()

        if not social_account:
            member = Member()
            db.add(member)
            db.flush()

            social = SocialAccount(
                member_id = member.id,
                provider = 'google',
                provider_id = provider_id
            )

            db.add(social)
            db.commit()

            temp_token = encode_temp_signup_token(member.id)

            res = RedirectResponse(url=f"{FRONTEND_URL}/#/signup?type=social")
            res.set_cookie(
                key="signup_token",
                value=temp_token,
                httponly=True,
                max_age=300
            )

        # 기존회원일 경우
        else:
            member = db.query(Member).filter(Member.id == social_account.member_id).first()

            if member.phone is None and member.name is None:
                temp_token = encode_temp_signup_token(member.id)
                res = RedirectResponse(url=f"{FRONTEND_URL}/#/signup?type=social")
                res.set_cookie(key="signup_token", value=temp_token, httponly=True, max_age=300)
                return res

            res = RedirectResponse(url=f"{FRONTEND_URL}/#/onboarding/member-type")
            add_token_for_cookie(social_account.member_id, db, res)
            return res


    except Exception as e:
        db.rollback()
        logger.exception("DB error")
        return JSONResponse(status_code=500, content={"error": "DB 오류"})
    
# ===================================================== 구글 로그인 ===================================================== #

# ===================================================== 애플 로그인 ===================================================== #
@router.get("/apple/login")
def apple_login():
    """
    ----------------------------------------
    애플 소셜로그인 API
    ----------------------------------------
    """
    state = str(uuid.uuid4())
    _state_store[state] = datetime.now() + timedelta(minutes=10)

    apple_auth_url = (
        f"https://appleid.apple.com/auth/authorize"
        f"?response_type=code"
        f"&client_id={APPLE_CLIENT_ID}"
        f"&redirect_uri={APPLE_REDIRECT_URI}"
        f"&scope=name%20email"
        f"&response_mode=form_post"   # ⚠️ 애플은 이게 필수 (form_post로만 콜백 옴)
        f"&state={state}"
    )

    return RedirectResponse(url=apple_auth_url)

@router.post("/apple/callback")  # ⚠️ 애플은 POST로 콜백이 옴 (구글은 GET)
async def apple_callback(
    code: str = Form(...),
    id_token: str = Form(None),
    state: str = Form(None),
    db: Session = Depends(get_db)
):
    """
    ----------------------------------------
    애플 소셜로그인 콜백 API
    ----------------------------------------
    """
    # # state 검증
    # if state not in _state_store or _state_store[state] < datetime.now():
    #     _state_store.pop(state, None)
    #     return JSONResponse(status_code=400, content={"error": "유효하지 않은 요청입니다."})

    # del _state_store[state]

    # client_secret 생성 (애플은 JWT로 동적 생성 필요)
    client_secret = _create_apple_client_secret()

    # 토큰 교환
    try:
        async with httpx.AsyncClient() as client:
            token_res = await client.post(
                "https://appleid.apple.com/auth/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": APPLE_CLIENT_ID,
                    "client_secret": client_secret,
                    "redirect_uri": APPLE_REDIRECT_URI,
                    "code": code,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10
            )

        if token_res.status_code != 200:
            logger.error(f"Apple token exchange failed: {token_res.text}")
            return JSONResponse(status_code=400, content={"error": "토큰 발급 실패"})

        token_json = token_res.json()
        id_token = token_json.get("id_token")
        if not id_token:
            return JSONResponse(status_code=400, content={"error": "토큰 없음"})

    except Exception as e:
        logger.error(f"Apple token request failed: {str(e)}")
        return JSONResponse(status_code=502, content={"error": "Apple 서버 오류"})

    # 사용자 정보 조회 (구글과 달리 id_token 디코딩으로 바로 획득, 별도 API 호출 없음)
    try:
        user_info = await _verify_apple_token(id_token)
    except Exception as e:
        logger.error(f"Apple token verify failed: {str(e)}")
        return JSONResponse(status_code=400, content={"error": "사용자 정보 조회 실패"})

    provider_id = user_info.get("sub")

    try:
        social_account = db.query(SocialAccount).filter(
            SocialAccount.provider == 'apple',
            SocialAccount.provider_id == str(provider_id)
        ).first()

        if not social_account:
            member = Member()
            db.add(member)
            db.flush()

            social = SocialAccount(
                member_id=member.id,
                provider='apple',
                provider_id=provider_id
            )
            db.add(social)
            db.commit()

            temp_token = encode_temp_signup_token(member.id)

            res = JSONResponse(content={"success": True, "redirect": "signup"})  # ← 변경
            res.set_cookie(key="signup_token", value=temp_token, httponly=True, max_age=300)
            return res

        else:
            member = db.query(Member).filter(Member.id == social_account.member_id).first()

            if member.phone is None and member.name is None:
                res = JSONResponse(content={"success": True, "redirect": "signup"})
                return res

            res = JSONResponse(content={"success": True, "redirect": "onboarding"})  # ← 변경
            add_token_for_cookie(social_account.member_id, db, res)
            return res

    except Exception as e:
        db.rollback()
        logger.exception("Apple DB error")
        return JSONResponse(status_code=500, content={"error": "DB 오류"})
    
def _create_apple_client_secret() -> str:
    payload = {
        "iss": APPLE_TEAM_ID,
        "iat": int(time.time()),
        "exp": int(time.time()) + 86400 * 180,  # 최대 6개월
        "aud": "https://appleid.apple.com",
        "sub": APPLE_CLIENT_ID,
    }
    return jwt.encode(
        payload,
        APPLE_PRIVATE_KEY,   # .p8 파일 내용 (문자열)
        algorithm="ES256",
        headers={"kid": APPLE_KEY_ID}
    )


async def _verify_apple_token(id_token: str) -> dict:
    # Apple 공개키 목록 조회
    async with httpx.AsyncClient() as client:
        res = await client.get("https://appleid.apple.com/auth/keys")
    keys = res.json()["keys"]

    # 토큰 헤더에서 kid 추출 후 매칭되는 공개키 선택
    header = jwt.get_unverified_header(id_token)
    public_key = None
    for key in keys:
        if key["kid"] == header["kid"]:
            public_key = RSAAlgorithm.from_jwk(json.dumps(key))
            break

    if not public_key:
        raise ValueError("Apple public key not found")

    return jwt.decode(
        id_token,
        public_key,
        algorithms=["RS256"],
        audience=APPLE_CLIENT_ID,
    )
# ===================================================== 애플 로그인 ===================================================== #