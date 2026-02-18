from fastapi import APIRouter
from sqlalchemy import text, func
from sqlalchemy.orm import Session
from database import get_db, SessionLocal
from firebase_init import send_push

from schemas.push import PushReq

router = APIRouter(prefix="/api/community", tags=["게시판"])

@router.post("")
def get_post_list(req: PushReq):
    """
    게시판 온보딩페이지 접속 시 호출되는 함수
    -> 글 목록 가져오기
    """

    if req.value == 1:
        body = "1입니다"
    elif req.value == 2:
        body = "2입니다"
    else:
        body = f"{req.value}입니다"
    
    result = send_push(req.token, "테스트 푸시", body)
    print(req.token)
    return {"sent": True, "body": body, "result": result}