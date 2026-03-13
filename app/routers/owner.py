import os
import httpx
import json
from fastapi import APIRouter, Depends, Query, Cookie, HTTPException, Response
from sqlalchemy import text, func
from sqlalchemy.orm import Session
from pathlib import Path
from dotenv import load_dotenv

from database import get_db, SessionLocal
from schemas.login import StoreInfo

ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(ENV_PATH)

BUSINESS_KEY = os.getenv("VITE_BUSINESS_API_KEY")

router = APIRouter(prefix="/api/owner", tags=["소셜 로그인 관리"])

 # ===================================================== 사업자번호 조회 ===================================================== #
@router.get("/business/{bno}")
async def verify_business(bno: str):
    """
    ----------------------------------------
    사업자등록번호 조회 API
    ----------------------------------------
    """
    
    url = "https://api.odcloud.kr/api/nts-businessman/v1/status"

    params = {
        "serviceKey": BUSINESS_KEY
    }

    data = {
        "b_no": [bno]
    }

    async with httpx.AsyncClient() as client:
        res = await client.post(
            url,
            params=params,
            json=data
        )

    return res.json()

@router.post("/stores")
def add_store_info(req: StoreInfo, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    매장정보 추가 API
    ----------------------------------------
    """

    print(req)