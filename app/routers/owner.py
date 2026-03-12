import os
import httpx
import json
from fastapi import APIRouter, Depends, Query, Cookie, HTTPException, Response
from sqlalchemy import text, func
from sqlalchemy.orm import Session
from pathlib import Path
from dotenv import load_dotenv

from database import get_db, SessionLocal

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

    print(bno)
    
    url = f"https://bizno.net/api/fapi?key={BUSINESS_KEY}&gb=3&q={bno}&type=json"

    async with httpx.AsyncClient() as client:
            res = await client.get(url)

    if "{" not in res.text:
        return {
            "error": "Bizno API error",
            "raw": res.text
        }

    return res.json()
