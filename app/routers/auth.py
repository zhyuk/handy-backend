import os
import httpx
import uuid
import logging
from fastapi import APIRouter, Depends, Query, Cookie, HTTPException, Response
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from sqlalchemy import text, func
from sqlalchemy.orm import Session
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timedelta

from models import Member, SocialAccount
from database import get_db, SessionLocal
from utils.auth_utils import normalize_phone, normalize_birth, convert_gender, password_encode, password_decode, generate_code, save_code, send_code_to_user, verify_code, check_daily_limit, add_token_for_cookie
from schemas.login import ValidLogin, Signup, PhoneReq, VerifyReq

logger = logging.getLogger(__name__)

ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(ENV_PATH)

KAKAO_CLIENT_ID = os.getenv("KAKAO_CLIENT_ID")
KAKAO_CLIENT_SECRET = os.getenv("KAKAO_CLIENT_SECRET")
KAKAO_REDIRECT_URI = os.getenv("KAKAO_REDIRECT_URI")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

router = APIRouter(prefix="/api/auth", tags=["소셜 로그인 관리"])

_state_store = {}

@router.post("/verify")
def verify_tokens(response: Response, ):
    """
    ----------------------------------------
    JWT 토큰 검증 API
    ----------------------------------------
    """
    pass 

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
        
@router.post("/signup/code/send")
def send_sms(req: PhoneReq):
    """
    ----------------------------------------
    회원가입용 인증코드 발송 API
    ----------------------------------------
    """
    phone = normalize_phone(req.phone)

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


@router.post("/signup")
def signup(req: Signup, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    회원가입 API
    ----------------------------------------
    """
    # existing = db.query(Member).filter(Member.phone == req.phone).first()

    # if existing:
    #     raise HTTPException(status_code=400, detail="이미 가입된 번호입니다.")

    phone = normalize_phone(req.phone)
    hashed_pw = password_encode(req.password)
    birth = normalize_birth(req.birth)
    gender = convert_gender(req.gender)

    member = Member(
        phone = phone,
        password = hashed_pw,
        name = req.name,
        birth = birth,
        gender = gender,
        # image_url = 
    )

    db.add(member)
    db.commit()

@router.post("/logout")
def logout():
    """
    ----------------------------------------
    로그아웃 API
    ----------------------------------------
    """
    pass



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
    
    # 신규가입 여부
    newly_created = False
    expires_in = int(token_json.get("expires_in", 6 * 60 * 60))

    try:
        socail_account = db.query(SocialAccount).filter(SocialAccount.provider == 'kakao').filter(SocialAccount.provider_id == str(provider_id)).first()

        if not socail_account:
            member = Member(
                phone = phone,
                name = name,
                birth = birthday,
                gender = gender,
            )
            db.add(member)
            db.flush()

            social = SocialAccount(
                member_id = member.id,
                provider = 'kakao',
                provider_id = provider_id
            )

            db.add(social)
            newly_created = True

        db.commit()

    except Exception as e:
        db.rollback()
        logger.exception("DB error")
        return JSONResponse(status_code=500, content={"error": "DB 오류"})
    
    # JWT 토큰 생성
        

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

    # 신규가입 여부
    newly_created = False
    expires_in = int(token_json.get("expires_in", 6 * 60 * 60))

    try:
        socail_account = db.query(SocialAccount).filter(SocialAccount.provider == 'google').filter(SocialAccount.provider_id == str(provider_id)).first()

        if not socail_account:
            member = Member()
            db.add(member)
            db.flush()

            social = SocialAccount(
                member_id = member.id,
                provider = 'google',
                provider_id = provider_id
            )

            db.add(social)
            newly_created = True

        db.commit()

    except Exception as e:
        db.rollback()
        logger.exception("DB error")
        return JSONResponse(status_code=500, content={"error": "DB 오류"})
    
    # JWT 토큰 생성


@router.get("/google/info")
async def google_callback(code: str, state: str, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    구글 소셜로그인 최초가입 시 추가정보 입력 API
    ----------------------------------------
    """



